"""
services/ai_service.py
Sugestão de alocação de tarefas e geração de seções textuais via Groq API (requests direto).
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


def _get_historicos() -> str:
    """Carrega texto dos briefings históricos do Drive (com cache)."""
    try:
        from services.drive_service import get_historicos_texto
        texto = get_historicos_texto(max_briefings=15)
        # Limita a ~8000 chars para não estourar o contexto do modelo
        if len(texto) > 8000:
            texto = texto[:8000] + "\n...[truncado]"
        return texto
    except Exception:
        return ""


def _chat(prompt: str) -> str:
    """Chama a API do Groq diretamente via requests e retorna o texto."""
    api_key = _get_secret("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY não configurada nos secrets.")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2000,
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Groq API erro {response.status_code}: {response.text}")

    return response.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Exemplos few-shot
# ---------------------------------------------------------------------------

FEW_SHOT_ALOCACAO = """
EXEMPLO 1 — Teste #03, Expominas, 11 membros:
Membros: João Gabriel Castelo (Capitania), Isis (Eletrônica), Gustavo Fornazier (Capitania),
Matheus de Paula (Dinâmica), Juliano Ornellas (Dinâmica), Gabriel (Motor),
Enrico (Freio), Bernardo (Aerodinâmica), Vinícius Ângelo (Chassi),
Guilherme Augusto (Freio), João Paulo (Dinâmica)
Validações: Validação do modelo VI Grade (SkidPad e Hairpin)
Resultado:
- João Gabriel Castelo → Piloto / Piloto
- Isis → (sem tarefa box) / Tempo de volta
- Gustavo Fornazier → Supervisão / Supervisão
- Matheus de Paula → Montagem Skid e Hairpin / Tempo de volta
- Juliano Ornellas → Montagem Skid e Hairpin / Posição B
- Gabriel → Warm Up / Posição B
- Enrico → (sem tarefa box) / Posição A
- Bernardo → Feedback de piloto / Tempo de volta
- Vinícius Ângelo → Limpeza da pista / Posição A
- Guilherme Augusto → Limpeza da pista / Posição A
- João Paulo → Montagem Skid e Hairpin / Posição B

EXEMPLO 2 — Teste #04, RBC, 7 membros:
Membros: Isis (Eletrônica), Eduardo (Freio), Lucas Herbert (Dinâmica),
Juliano (Dinâmica), João Pedro Santos (Motor), Bernardo Gásparo (Aerodinâmica),
Gustavo Fornazier (Capitania)
Validações: Validação do Modelo VI Grade em Circuito
Resultado:
- Isis → (sem tarefa box) / Tempo de volta
- Eduardo → Auxílio montagem / Posição A
- Lucas Herbert → Piloto / Piloto
- Juliano → Montagem / Montagem
- João Pedro Santos → Warm Up / Tempo de volta
- Bernardo Gásparo → Feedback de Piloto / Posição B
- Gustavo Fornazier → Supervisão / Supervisão

EXEMPLO 3 — Teste #05, RBC, 13 membros:
Membros: Alexandre (Transmissão), Arthur (Chassi), Eduardo Scherrer (Motor),
Enrico Meniconi (Freio), Fabio Moriya (Freio), Gustavo Alcantara (Chassi),
Gustavo Fornazier (Capitania), Isis (Eletrônica), João Gabriel (Capitania),
Luis Filipe Milione (Eletrônica, piloto), Maria Clara (Chassi), Pedro Flauzino (Transmissão)
Validações: Ensaio de pilotos
Resultado:
- Alexandre → Montagem A / Setor 1
- Arthur → Montagem B / Setor 2
- Eduardo Scherrer → Warm Up / Setor 3
- Enrico Meniconi → Montagem C / Setor 4
- Fabio Moriya → Montagem D / Setor 5
- Gustavo Alcantara → Montagem A / Setor 6
- Gustavo Fornazier → Montagem B / Setor 1/Piloto 2
- Isis → (sem tarefa box) / Setor 2
- João Gabriel → Supervisão / Setor 1
- Luis Filipe Milione → Piloto 1 / Piloto 1/Setor 3
- Maria Clara → Montagem C / Setor 4
- Pedro Flauzino → Montagem D / Setor 5
"""


# ---------------------------------------------------------------------------
# Sugestão de alocação de tarefas
# ---------------------------------------------------------------------------

def suggest_task_allocation(
    membros: list[dict],
    validacoes: list[dict],
    pilotos_escolhidos: list[str],
    local: str,
    circuito: str,
) -> list[dict]:

    def _match_piloto(nome: str, pilotos: list[str]) -> bool:
        n = nome.lower()
        for p in pilotos:
            p_lower = p.lower()
            if p_lower in n or n in p_lower:
                return True
            for palavra in p_lower.split():
                if len(palavra) > 3 and palavra in n:
                    return True
        return False

    membros_str = "\n".join(
        f"- {m['nome']} ({m['subgrupo']})"
        + (f", chega {m['chegada']}" if m.get("chegada") else "")
        + (f", sai {m['saida']}" if m.get("saida") else "")
        + (" [PILOTO DESIGNADO]" if _match_piloto(m["nome"], pilotos_escolhidos) else "")
        for m in membros
    )

    validacoes_str = "\n".join(
        f"- {v['nome']} (subgrupo: {v['subgrupo']})"
        for v in validacoes
    )

    prompt = f"""Você é engenheira de corrida da equipe Formula SAE UFMG.
Sugira a alocacao de tarefas para o dia de teste.

REGRAS:
1. Capitania -> Supervisao (pelo menos um)
2. Motor -> Warm Up (obrigatorio pelo menos um)
3. Dinamica e Eletronica -> preferencialmente Warm Up
4. Freio -> setor de frenagem
5. Pilotos designados recebem tarefa "Piloto" em ambas as colunas (tarefa_box="Piloto", tarefa_pista="Piloto")
6. Membros com chegada tardia podem ficar sem tarefa de box
7. Membros que nao estao em Supervisao nem Warm Up devem ser distribuidos entre as montagens (Montagem A, B, C, D)
8. "Feedback de piloto" e sempre tarefa de PISTA (tarefa_pista), nunca de box

LOCAL: {local}
CIRCUITO: {circuito}

MEMBROS:
{membros_str}

VALIDACOES:
{validacoes_str}

EXEMPLOS DE ALOCACAO DE BRIEFINGS ANTERIORES:
{FEW_SHOT_ALOCACAO}

BRIEFINGS HISTORICOS COMPLETOS PARA REFERENCIA:
{_get_historicos()}

Responda APENAS com JSON valido, sem texto, sem markdown, sem backticks.
Formato: {{"alocacao": [{{"nome": "Nome", "tarefa_box": "tarefa", "tarefa_pista": "tarefa", "piloto": false}}]}}"""

    try:
        raw = _chat(prompt)
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        alocacao_map = {a["nome"]: a for a in data["alocacao"]}
        for m in membros:
            if m["nome"] in alocacao_map:
                a = alocacao_map[m["nome"]]
                # Só atualiza tarefas — subgrupo, chegada e saída vêm do Notion
                m["tarefa_box"] = a.get("tarefa_box", "")
                m["tarefa_pista"] = a.get("tarefa_pista", "")
                m["piloto"] = a.get("piloto", False)
    except Exception as e:
        raise RuntimeError(f"Erro na sugestão de alocação: {e}") from e

    return membros


# ---------------------------------------------------------------------------
# Geração das seções textuais
# ---------------------------------------------------------------------------

def generate_briefing_sections(validacoes: list[dict]) -> dict:

    validacoes_str = "\n\n".join(
        f"VALIDACAO: {v['nome']}\n"
        f"Objetivos: {v.get('objetivos', '')}\n"
        f"Hipotese: {v.get('hipotese', '')}\n"
        f"Revisao teorica: {v.get('revisao_teorica', '')}\n"
        f"Procedimento: {v.get('procedimento', '')}"
        for v in validacoes
    )

    prompt = f"""Voce e engenheira de corrida da equipe Formula SAE UFMG.
Estilo: tecnico, direto, terminologia de engenharia automotiva, em portugues.
Use os briefings historicos abaixo como referencia de estilo, nivel tecnico e estrutura.

BRIEFINGS HISTORICOS PARA REFERENCIA DE ESTILO:
{_get_historicos()}

VALIDACOES DO DIA:
{validacoes_str}

Gere 3 secoes no mesmo estilo dos briefings historicos:
- "o_que_buscamos": resumo dos objetivos e hipoteses, 2-4 paragrafos, mencione KPIs se houver
- "entenda_o_teste": contexto teorico acessivel a todos, 2-3 paragrafos
- "procedimento": passos numerados consolidando os procedimentos

Responda APENAS com JSON valido, sem texto, sem markdown, sem backticks.
Formato: {{"o_que_buscamos": "texto", "entenda_o_teste": "texto", "procedimento": "1. passo\\n2. passo"}}"""

    try:
        raw = _chat(prompt)
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Erro na geração de seções: {e}") from e


# ---------------------------------------------------------------------------
# Geração do cronograma
# ---------------------------------------------------------------------------

def generate_schedule(local: str, validacoes: list[dict], num_pilotos: int) -> list[dict]:
    local_lower = local.lower()

    if "rbc" in local_lower or "kart" in local_lower:
        base = [
            {"atividade": "CHEGADA NA OFICINA",      "horario": "09h30", "comentario": ""},
            {"atividade": "SAÍDA DA OFICINA",         "horario": "10h30", "comentario": ""},
            {"atividade": "CHEGADA NO LOCAL",         "horario": "11h00", "comentario": ""},
            {"atividade": "BRIEFING",                 "horario": "11h10 – 11h15", "comentario": ""},
            {"atividade": "WARM UP E AJUSTES",        "horario": "11h15 – 11h50", "comentario": ""},
        ]
        hora = 12 * 60
        for i in range(num_pilotos):
            inicio = f"{hora//60:02d}h{hora%60:02d}"
            hora += 30
            fim = f"{hora//60:02d}h{hora%60:02d}"
            comentario = "*Sobrando tempo, próximo piloto entra" if i < num_pilotos - 1 else ""
            base.append({"atividade": f"EM PISTA – PILOTO {i+1}", "horario": f"{inicio} – {fim}", "comentario": comentario})
        base += [
            {"atividade": "RETORNO PRO BOX",                  "horario": f"{hora//60:02d}h{hora%60:02d}", "comentario": ""},
            {"atividade": "ORGANIZAÇÃO P/ RETORNO À OFICINA", "horario": f"{hora//60:02d}h{hora%60:02d} – {(hora+20)//60:02d}h{(hora+20)%60:02d}", "comentario": ""},
            {"atividade": "DEBRIEFING",                       "horario": f"{(hora+20)//60:02d}h{(hora+20)%60:02d} – {(hora+25)//60:02d}h{(hora+25)%60:02d}", "comentario": ""},
            {"atividade": "SAÍDA DO LOCAL",                   "horario": f"{(hora+30)//60:02d}h{(hora+30)%60:02d}", "comentario": ""},
            {"atividade": "CHEGADA NA OFICINA",               "horario": f"{(hora+60)//60:02d}h{(hora+60)%60:02d}", "comentario": ""},
        ]
        return base

    return [
        {"atividade": "CHEGADA NA OFICINA",        "horario": "08h00", "comentario": ""},
        {"atividade": "SAÍDA DA OFICINA",           "horario": "09h00", "comentario": ""},
        {"atividade": "CHEGADA NO LOCAL",           "horario": "09h30", "comentario": ""},
        {"atividade": "DESCARREGAR, MONTAR TENDA",  "horario": "09h30 – 10h00", "comentario": ""},
        {"atividade": "BRIEFING",                   "horario": "10h00 – 10h10", "comentario": ""},
        {"atividade": "WARM UP E AJUSTES",          "horario": "10h10 – 10h40", "comentario": ""},
        {"atividade": "SESSÃO PRINCIPAL",           "horario": "10h40 – 12h00", "comentario": ""},
        {"atividade": "PAUSA PARA ALMOÇO",          "horario": "12h00 – 13h00", "comentario": ""},
        {"atividade": "SESSÃO TARDE",               "horario": "13h00 – 14h30", "comentario": ""},
        {"atividade": "ORGANIZAR P/ RETORNO",       "horario": "16h00 – 16h30", "comentario": ""},
        {"atividade": "SAÍDA DO LOCAL",             "horario": "16h30", "comentario": ""},
        {"atividade": "CHEGADA NA OFICINA",         "horario": "17h00", "comentario": ""},
    ]