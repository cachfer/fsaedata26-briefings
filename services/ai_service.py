"""
services/ai_service.py
Sugestão de alocação de tarefas e geração das seções textuais via Anthropic API.
"""

import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

client = anthropic.Anthropic(api_key=_get_secret("ANTHROPIC_API_KEY"))

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
- João Gabriel Castelo → Piloto / Piloto (capitania pode pilotar)
- Isis → (sem tarefa box) / Tempo de volta
- Gustavo Fornazier → Supervisão / Supervisão
- Matheus de Paula → Montagem Skid e Hairpin / Tempo de volta
- Juliano Ornellas → Montagem Skid e Hairpin / Posição B
- Gabriel → Warm Up / Posição B (Motor obrigatório no warm up)
- Enrico → (sem tarefa box) / Posição A (chegada tardia)
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
- Isis → (sem tarefa box) / Tempo de volta (chegada tardia)
- Eduardo → Auxílio montagem / Posição A
- Lucas Herbert → Piloto / Piloto
- Juliano → Montagem / Montagem
- João Pedro Santos → Warm Up / Tempo de volta (Motor no warm up)
- Bernardo Gásparo → Feedback de Piloto / Posição B
- Gustavo Fornazier → Supervisão / Supervisão (Capitania na supervisão)

EXEMPLO 3 — Teste #05, RBC, 13 membros:
Membros: Alexandre (Transmissão), Arthur (Chassi), Eduardo Scherrer (Motor),
Enrico Meniconi (Freio), Fabio Moriya (Freio), Gustavo Alcantara (Chassi),
Gustavo Fornazier (Capitania), Isis (Eletrônica), João Gabriel (Capitania),
Luis Filipe Milione (Eletrônica, piloto), Maria Clara (Chassi), Pedro Flauzino (Transmissão)
Validações: Ensaio de pilotos
Resultado:
- Alexandre → Montagem A / Setor 1
- Arthur → Montagem B / Setor 2
- Eduardo Scherrer → Warm Up / Setor 3 (Motor obrigatório no warm up)
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
    """
    Usa a IA para sugerir tarefa_box e tarefa_pista para cada membro.
    Retorna a lista de membros com os campos preenchidos.
    """
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
Sua tarefa é sugerir a alocação de tarefas para o dia de teste com base nas informações abaixo.

REGRAS OBRIGATÓRIAS:
1. Capitania → Supervisão (pelo menos um membro da capitania DEVE estar na supervisão)
2. Motor → Warm Up (pelo menos um membro do subgrupo Motor DEVE estar no warm up)
3. Dinâmica e Eletrônica → preferencialmente no Warm Up
4. Freio → preferencialmente no setor/posição de frenagem
5. Pilotos designados recebem tarefa "Piloto" em ambas as colunas
6. Membros com chegada tardia podem ficar sem tarefa de box ou com tarefa de pista apenas

LOCAL: {local}
CIRCUITO: {circuito}

MEMBROS CONFIRMADOS:
{membros_str}

VALIDAÇÕES DO DIA:
{validacoes_str}

REFERÊNCIAS DE ALOCAÇÕES ANTERIORES:
{FEW_SHOT_ALOCACAO}

Responda APENAS com um JSON válido, sem texto adicional, no seguinte formato:
{{
  "alocacao": [
    {{
      "nome": "Nome do membro",
      "tarefa_box": "tarefa ou vazio",
      "tarefa_pista": "tarefa ou vazio",
      "piloto": true/false
    }}
  ]
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
        alocacao_map = {a["nome"]: a for a in data["alocacao"]}
        for m in membros:
            if m["nome"] in alocacao_map:
                a = alocacao_map[m["nome"]]
                m["tarefa_box"] = a.get("tarefa_box", "")
                m["tarefa_pista"] = a.get("tarefa_pista", "")
                m["piloto"] = a.get("piloto", False)
    except (json.JSONDecodeError, KeyError):
        pass  # Mantém campos vazios se a IA falhar

    return membros


# ---------------------------------------------------------------------------
# Geração das seções textuais
# ---------------------------------------------------------------------------

def generate_briefing_sections(validacoes: list[dict]) -> dict:
    """
    Gera as seções 'O que buscamos atingir' e 'Entenda o teste'
    a partir das metodologias das validações do dia.
    """
    validacoes_str = "\n\n".join(
        f"VALIDAÇÃO: {v['nome']}\n"
        f"Objetivos: {v.get('objetivos', '')}\n"
        f"Hipótese: {v.get('hipotese', '')}\n"
        f"Revisão teórica: {v.get('revisao_teorica', '')}\n"
        f"Procedimento: {v.get('procedimento', '')}"
        for v in validacoes
    )

    prompt = f"""Você é engenheira de corrida da equipe Fórmula UFMG.
Seu estilo de escrita é técnico, direto e objetivo, usando terminologia de engenharia automotiva.
Você está gerando o conteúdo para um briefing de teste.

DADOS DAS VALIDAÇÕES DO DIA:
{validacoes_str}

Gere o conteúdo para duas seções do briefing, em português, seguindo exatamente o formato abaixo.

A seção "O QUE BUSCAMOS ATINGIR" deve resumir os objetivos e hipóteses de todas as validações
em 2-4 parágrafos coesos. Mencione os KPIs relevantes se houver.

A seção "ENTENDA O TESTE" deve explicar o contexto teórico de forma acessível a todos os
membros da equipe (não só aos especialistas), em 2-3 parágrafos.

A seção "PROCEDIMENTO EM PISTA" deve consolidar os procedimentos das validações em
passos numerados claros.

Responda APENAS com JSON válido, sem texto adicional:
{{
  "o_que_buscamos": "texto da seção...",
  "entenda_o_teste": "texto da seção...",
  "procedimento": "texto do procedimento..."
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "o_que_buscamos": "",
            "entenda_o_teste": "",
            "procedimento": "",
        }


# ---------------------------------------------------------------------------
# Geração do cronograma
# ---------------------------------------------------------------------------

def generate_schedule(
    local: str,
    validacoes: list[dict],
    num_pilotos: int,
) -> list[dict]:
    """
    Gera o cronograma padrão ajustado pelo local e número de pilotos.
    Retorna lista de {atividade, horario, comentario}.
    """
    # Horários base para RBC (circuito enduro/dia normal)
    if "rbc" in local.lower() or "kartodromo" in local.lower():
        base = [
            {"atividade": "CHEGADA NA OFICINA",       "horario": "09h30", "comentario": ""},
            {"atividade": "SAÍDA DA OFICINA",          "horario": "10h30", "comentario": ""},
            {"atividade": "CHEGADA NO LOCAL",          "horario": "11h00", "comentario": ""},
            {"atividade": "BRIEFING",                  "horario": "11h10 – 11h15", "comentario": ""},
            {"atividade": "WARM UP E AJUSTES",         "horario": "11h15 – 11h50", "comentario": ""},
        ]
        # Adiciona sessões por piloto
        hora_atual = 12 * 60  # 12h00 em minutos
        for i in range(num_pilotos):
            label = f"EM PISTA – PILOTO {i+1}"
            inicio = f"{hora_atual // 60:02d}h{hora_atual % 60:02d}"
            hora_atual += 30
            fim = f"{hora_atual // 60:02d}h{hora_atual % 60:02d}"
            base.append({
                "atividade": label,
                "horario": f"{inicio} – {fim}",
                "comentario": "*Sobrando tempo, próximo piloto entra" if i < num_pilotos - 1 else "",
            })

        base += [
            {"atividade": "RETORNO PRO BOX",                  "horario": f"{hora_atual // 60:02d}h{hora_atual % 60:02d}", "comentario": ""},
            {"atividade": "ORGANIZAÇÃO P/ RETORNO À OFICINA", "horario": f"{hora_atual // 60:02d}h{hora_atual % 60:02d} – {(hora_atual + 20) // 60:02d}h{(hora_atual + 20) % 60:02d}", "comentario": ""},
            {"atividade": "DEBRIEFING",                       "horario": f"{(hora_atual + 20) // 60:02d}h{(hora_atual + 20) % 60:02d} – {(hora_atual + 25) // 60:02d}h{(hora_atual + 25) % 60:02d}", "comentario": ""},
            {"atividade": "SAÍDA DO LOCAL",                   "horario": f"{(hora_atual + 30) // 60:02d}h{(hora_atual + 30) % 60:02d}", "comentario": ""},
            {"atividade": "CHEGADA NA OFICINA",               "horario": f"{(hora_atual + 60) // 60:02d}h{(hora_atual + 60) % 60:02d}", "comentario": ""},
        ]
        return base

    # Horários base para Expominas (dia longo)
    return [
        {"atividade": "CHEGADA NA OFICINA",          "horario": "08h00", "comentario": ""},
        {"atividade": "SAÍDA DA OFICINA",             "horario": "09h00", "comentario": ""},
        {"atividade": "CHEGADA NO LOCAL",             "horario": "09h30", "comentario": ""},
        {"atividade": "DESCARREGAR, MONTAR TENDA",    "horario": "09h30 – 10h00", "comentario": ""},
        {"atividade": "BRIEFING",                     "horario": "10h00 – 10h10", "comentario": ""},
        {"atividade": "WARM UP E AJUSTES",            "horario": "10h10 – 10h40", "comentario": ""},
        {"atividade": "SESSÃO PRINCIPAL",             "horario": "10h40 – 12h00", "comentario": ""},
        {"atividade": "PAUSA PARA ALMOÇO",            "horario": "12h00 – 13h00", "comentario": ""},
        {"atividade": "SESSÃO TARDE",                 "horario": "13h00 – 14h30", "comentario": ""},
        {"atividade": "ORGANIZAR P/ RETORNO",         "horario": "16h00 – 16h30", "comentario": ""},
        {"atividade": "SAÍDA DO LOCAL",               "horario": "16h30", "comentario": ""},
        {"atividade": "CHEGADA NA OFICINA",           "horario": "17h00", "comentario": ""},
    ]
