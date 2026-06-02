"""
services/notion_service.py
Leitura de dados do Notion: testes, metodologias e formulários de comparecimento.
"""

import os
from datetime import datetime, date, timedelta
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


notion = Client(auth=_get_secret("NOTION_TOKEN"))
TESTES_DB = _get_secret("NOTION_TESTES_DB_ID")
METODOLOGIAS_DB = _get_secret("NOTION_METODOLOGIAS_DB_ID")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(prop) -> str:
    if not prop:
        return ""
    # rich_text e title
    content = prop.get("rich_text") or prop.get("title") or []
    if content:
        return "".join(c.get("plain_text", "") for c in content)
    # number
    if prop.get("number") is not None:
        return str(prop["number"])
    # phone_number
    if prop.get("phone_number"):
        return str(prop["phone_number"])
    # email
    if prop.get("email"):
        return str(prop["email"])
    return ""


def _select(prop) -> str:
    if not prop or not prop.get("select"):
        return ""
    return prop["select"]["name"]


def _date(prop) -> str:
    if not prop or not prop.get("date"):
        return ""
    return prop["date"]["start"]


def _relation_ids(prop) -> list[str]:
    if not prop:
        return []
    return [r["id"] for r in prop.get("relation", [])]


def _url(prop) -> str:
    if not prop:
        return ""
    return prop.get("url") or ""


def _number(prop):
    if not prop:
        return None
    return prop.get("number")


def _created_time(page) -> date | None:
    """Pega a data de criação da página (sempre disponível no Notion)."""
    ct = page.get("created_time", "")
    if ct:
        return datetime.fromisoformat(ct.replace("Z", "+00:00")).date()
    return None


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def get_test_dates() -> list[date]:
    """Retorna lista de datas com testes cadastrados no Notion, ordenadas."""
    results = notion.databases.query(
        database_id=TESTES_DB,
        sorts=[{"property": "Data", "direction": "ascending"}],
    )["results"]

    dates = []
    for page in results:
        props = page["properties"]
        raw = _date(props.get("Data"))
        if raw:
            dates.append(datetime.fromisoformat(raw).date())
    return sorted(set(dates))


def get_test_by_date(target_date: date) -> dict | None:
    """Busca o teste cuja data corresponde a target_date."""
    results = notion.databases.query(
        database_id=TESTES_DB,
        filter={
            "property": "Data",
            "date": {"equals": target_date.isoformat()},
        },
    )["results"]

    if not results:
        return None

    page = results[0]
    props = page["properties"]
    validacao_ids = _relation_ids(props.get("Validações"))

    return {
        "id": page["id"],
        "numero": _number(props.get("Número")) or _number(props.get("Numero")) or "",
        "data": target_date,
        "local": _text(props.get("Local")) or _select(props.get("Local")),
        "circuito": _select(props.get("Circuito")) or _text(props.get("Circuito")),
        "responsavel": _text(props.get("Responsável")) or "Carolina Ferrari",
        "validacao_ids": validacao_ids,
    }


# ---------------------------------------------------------------------------
# Metodologias / Validações
# ---------------------------------------------------------------------------

def get_metodologia(page_id: str) -> dict:
    """Busca uma validação/metodologia pelo ID da página no Notion."""
    page = notion.pages.retrieve(page_id=page_id)
    props = page["properties"]

    return {
        "id": page_id,
        "nome": _text(props.get("Validação")) or _text(props.get("Nome")) or _text(props.get("Validacao")),
        "subgrupo": _select(props.get("Subgrupo")),
        "metodologia_url": _url(props.get("Metodologia")),
        "objetivos": _text(props.get("Objetivos")),
        "hipotese": _text(props.get("Hipótese")) or _text(props.get("Hipotese")),
        "revisao_teorica": _text(props.get("Revisão Teórica")) or _text(props.get("Revisao Teorica")),
        "procedimento": _text(props.get("Procedimento em Pista")) or _text(props.get("Procedimento")),
    }


def get_validacoes_do_teste(validacao_ids: list[str]) -> list[dict]:
    """Retorna todas as validações associadas a um teste."""
    return [get_metodologia(vid) for vid in validacao_ids]


# ---------------------------------------------------------------------------
# Formulário de comparecimento
# ---------------------------------------------------------------------------

def _get_comparecimento_db_id(local: str, data: date) -> str | None:
    """
    Mapeia (local, dia da semana) para o ID do banco de dados
    do formulário de comparecimento.
    """
    dias = {0: "SEG", 1: "TER", 2: "QUA", 3: "QUI", 4: "SEX", 5: "SAB", 6: "DOM"}
    dia = dias[data.weekday()]

    local_upper = local.upper().strip()
    if "RBC" in local_upper or "KART" in local_upper:
        local_key = "RBC"
    elif "EXPOMINAS" in local_upper or "EXPO" in local_upper:
        local_key = "EXPOMINAS"
    else:
        local_key = local_upper.replace(" ", "_")

    env_key = f"COMPARECIMENTO_{local_key}_{dia}"
    return _get_secret(env_key)


def _find_prop(props: dict, candidates: list[str]) -> any:
    """Tenta várias variações de nome de coluna e retorna a primeira que existir."""
    for name in candidates:
        if name in props:
            return props[name]
    return None


def get_membros_confirmados(local: str, data: date) -> list[dict]:
    """
    Retorna membros que confirmaram presença no formulário
    correspondente ao local e data do teste.
    Filtra preenchimentos entre domingo anterior e o dia do teste.
    """
    db_id = _get_comparecimento_db_id(local, data)
    if not db_id:
        return []

    # Janela: de domingo da semana do teste até o dia do teste
    dias_desde_domingo = (data.weekday() + 1) % 7
    domingo = data - timedelta(days=dias_desde_domingo)

    # Busca sem ordenar por campo específico — usa created_time depois
    try:
        results = notion.databases.query(
            database_id=db_id,
            filter={
                "and": [
                    {
                        "timestamp": "created_time",
                        "created_time": {"on_or_after": domingo.isoformat()},
                    },
                    {
                        "timestamp": "created_time",
                        "created_time": {"on_or_before": data.isoformat()},
                    },
                ]
            },
        )["results"]
    except Exception:
        # Fallback sem filtro de data se a API não suportar
        results = notion.databases.query(database_id=db_id)["results"]

    membros = []
    nomes_vistos = set()

    # Ordena por created_time decrescente para pegar o preenchimento mais recente
    results.sort(
        key=lambda p: p.get("created_time", ""),
        reverse=True,
    )

    for page in results:
        props = page["properties"]

        # Nome — tenta várias variações
        nome_prop = _find_prop(props, ["Nome", "Name", "nome", "NOME"])
        nome = _text(nome_prop)
        if not nome:
            continue

        # Pega só o preenchimento mais recente por pessoa
        if nome in nomes_vistos:
            continue
        nomes_vistos.add(nome)

        # Subgrupo — select no Notion
        subgrupo_prop = _find_prop(props, [
            "Subgrupo", "subgrupo", "Sub-grupo", "Grupo", "grupo"
        ])
        subgrupo = _select(subgrupo_prop) or _text(subgrupo_prop)

        # Carro
        carro_prop = _find_prop(props, [
            "Você vai com o seu carro?",
            "Vai de carro?",
            "Carro",
            "carro",
            "Tem carro?",
        ])
        carro_valor = _select(carro_prop) or _text(carro_prop)
        tem_carro = carro_valor.strip().lower() in ("sim", "yes", "s")

        # Chegada / Saída — nomes exatos do formulário
        chegada_prop = _find_prop(props, [
            "Que horas você pretende chegar?",
            "Que horas você chega?",
            "Chegada", "chegada", "Horário de chegada",
        ])
        saida_prop = _find_prop(props, [
            "Que horas você pretende sair?",
            "Que horas você sai?",
            "Saída", "saida", "Horário de saída",
        ])

        # Chegada e saída podem ser rich_text, select ou number
        chegada = _text(chegada_prop) or _select(chegada_prop)
        saida = _text(saida_prop) or _select(saida_prop)

        membros.append({
            "nome": nome,
            "subgrupo": subgrupo,
            "tem_carro": tem_carro,
            "chegada": chegada,
            "saida": saida,
            "tarefa_box": "",
            "tarefa_pista": "",
            "piloto": False,
        })

    return membros


# ---------------------------------------------------------------------------
# Debug: lista todas as propriedades de um database
# (útil para descobrir nomes exatos das colunas)
# ---------------------------------------------------------------------------

def debug_db_properties(db_id: str) -> dict:
    """Retorna as propriedades de um database para debug."""
    db = notion.databases.retrieve(database_id=db_id)
    return {k: v["type"] for k, v in db.get("properties", {}).items()}