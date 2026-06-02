"""
services/ai_service.py
Sugestão de alocação de tarefas e geração das seções textuais via Groq API.
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


def _get_client() -> Groq:
    api_key = _get_secret("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY não configurada nos secrets.")
    return Groq(api_key=api_key)


def _chat(prompt: str) -> str:
    """Envia um prompt para o Groq e retorna o texto da resposta."""
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Exemplos few-shot extraídos dos briefings históricos
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
- Gabriel → Warm Up / Posição B (Motor obrigatório no warm up)
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
    membros_str = "\n".join(
        f"- {m['nome']} ({m['subgrupo']})"
        + (f", chega {m['chegada']}" if m.get("chegada") else "")
        + (f", sai {m['saida']}" if m.get("saida") else "")
        + (" [PILOTO DESIGNADO]" if m["nome"] in pilotos_escolhidos else "")
        for m in membros
    )

    validacoes_str = "\n".join(
        f"- {v['nome']} (subgrupo: {v['subgrupo']})"
        for v in validacoes
    )

    prompt = f"""Você é engenheira de corrida da equipe Fórmula SAE UFMG.
Sugira a alocação de tarefas para o dia de teste com base nas informações abaixo.

REGRAS OBRIGATÓRIAS:
1. Capitania → Supervisão (pelo menos um DEVE estar na supervisão)
2. Motor → Warm Up (pelo menos um DEVE estar no warm up)
3. Dinâmica e Eletrônica → preferencialmente no Warm Up
4. Freio → preferencialmente no setor/posição de frenagem
5. Pilotos designados recebem tarefa "Piloto" em ambas as colunas
6. Membros com chegada tardia podem ficar sem tarefa de box

LOCAL: {local}
CIRCUITO: {circuito}

MEMBROS CONFIRMADOS:
{membros_str}

VALIDAÇÕES DO DIA:
{validacoes_str}

REFERÊNCIAS DE ALOCAÇÕES ANTERIORES:
{FEW_SHOT_ALOCACAO}

Responda APENAS com JSON válido, sem texto adicional, sem markdown, sem backticks.
Formato exato:
{{"alocacao": [{{"nome": "Nome do membro", "tarefa_box": "tarefa ou vazio", "tarefa_pista": "tarefa ou vazio", "piloto": false}}]}}
"""

    try:
        raw = _chat(prompt)
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        alocacao_map = {a["nome"]: a for a in data["alocacao"]}
        for m in membros:
            if m["nome"] in alocacao_map:
                a = alocacao_map[m["nome"]]
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
        f"VALIDAÇÃO: {v['nome']}\n"
        f"Objetivos: {v.get('objetivos', '')}\n"
        f"Hipótese: {v.get('hipotese', '')}\n"
        f"Revisão teórica: {v.get('revisao_teorica', '')}\n"
        f"Procedimento: {v.get('procedimento', '')}"
        for v in validacoes
    )

    prompt = f"""Você é engenheira de corrida da equipe Fórmula SAE UFMG.
Estilo: técnico, direto, terminologia de engenharia automotiva, em português.

DADOS DAS VALIDAÇÕES DO DIA:
{validacoes_str}

Gere conteúdo para três seções do briefing:

"O QUE BUSCAMOS ATINGIR": resumo dos objetivos e hipóteses em 2-4 parágrafos. Mencione KPIs se houver.
"ENTENDA O TESTE": contexto teórico acessível a todos os membros, 2-3 parágrafos.
"PROCEDIMENTO EM PISTA": passos numerados consolidando os procedimentos.

Responda APENAS com JSON válido, sem texto adicional, sem markdown, sem backticks.
Formato exato:
{{"o_que_buscamos": "texto...", "entenda_o_teste": "texto...", "procedimento": "1. passo\\n2. passo\\n3. passo"}}
"""

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

    if "rbc" in local_lower or "kartodromo" in local_lower or "kartódromo" in local_lower:
        base = [
            {"atividade": "CHEGADA NA OFICINA",      "horario": "09h30", "comentario": ""},
            {"atividade": "SAÍDA DA OFICINA",         "horario": "10h30", "comentario": ""},
            {"atividade": "CHEGADA NO LOCAL",         "horario": "11h00", "comentario": ""},
            {"atividade": "BRIEFING",                 "horario": "11h10 – 11h15", "comentario": ""},
            {"atividade": "WARM UP E AJUSTES",        "horario": "11h15 – 11h50", "comentario": ""},
        ]
        hora = 12 * 60
        for i in range(num_pilotos):
            inicio = f"{hora // 60:02d}h{hora % 60:02d}"
            hora += 30
            fim = f"{hora // 60:02d}h{hora % 60:02d}"
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