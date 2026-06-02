"""
services/notion_service.py
Leitura de dados do Notion: testes, metodologias e formulários de comparecimento.
"""

import os
from datetime import datetime, date
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
    """Extrai texto de uma propriedade rich_text ou title do Notion."""
    if not prop:
        return ""
    content = prop.get("rich_text") or prop.get("title") or []
    return "".join(c.get("plain_text", "") for c in content)


def _select(prop) -> str:
    if not prop or not prop.get("select"):
        return ""
    return prop["select"]["name"]


def _multi_select(prop) -> list[str]:
    if not prop:
        return []
    return [o["name"] for o in prop.get("multi_select", [])]


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

    # IDs das validações relacionadas
    validacao_ids = _relation_ids(props.get("Validações"))

    return {
        "id": page["id"],
        "numero": _number(props.get("Número")) or "",
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
        "nome": _text(props.get("Validação")) or _text(props.get("Nome")),
        "subgrupo": _select(props.get("Subgrupo")),
        "metodologia_url": _url(props.get("Metodologia")),
        "objetivos": _text(props.get("Objetivos")),
        "hipotese": _text(props.get("Hipótese")),
        "revisao_teorica": _text(props.get("Revisão Teórica")),
        "procedimento": _text(props.get("Procedimento em Pista")),
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
    local_key = local.upper().replace(" ", "_").replace("Á", "A").replace("ó", "O")

    # Normaliza nomes conhecidos
    if "RBC" in local_key or "KARTODROMO" in local_key:
        local_key = "RBC"
    elif "EXPOMINAS" in local_key:
        local_key = "EXPOMINAS"

    env_key = f"COMPARECIMENTO_{local_key}_{dia}"
    return os.environ.get(env_key)


def get_membros_confirmados(local: str, data: date) -> list[dict]:
    """
    Retorna membros que confirmaram presença no formulário
    correspondente ao local e data do teste.
    """
    db_id = _get_comparecimento_db_id(local, data)
    if not db_id:
        return []

    # Filtra pelo formulário mais recente (data de preenchimento <= data do teste)
    results = notion.databases.query(
        database_id=db_id,
        sorts=[{"property": "Data de preenchimento", "direction": "descending"}],
    )["results"]

    membros = []
    for page in results:
        props = page["properties"]

        # Pega só respostas preenchidas antes ou no dia do teste
        preenchido_em = _date(props.get("Data de preenchimento"))
        if preenchido_em:
            preenchido_date = datetime.fromisoformat(preenchido_em).date()
            if preenchido_date > data:
                continue

        nome = _text(props.get("Nome"))
        if not nome:
            continue

        membros.append({
            "nome": nome,
            "subgrupo": _select(props.get("Subgrupo")) or _text(props.get("Subgrupo")),
            "tem_carro": _select(props.get("Você vai com o seu carro?")) == "Sim",
            "chegada": _text(props.get("Que horas você chega?")),
            "saida": _text(props.get("Que horas você sai?")),
            # Campos que serão preenchidos pela IA / admin
            "tarefa_box": "",
            "tarefa_pista": "",
            "piloto": False,
        })

    return membros
