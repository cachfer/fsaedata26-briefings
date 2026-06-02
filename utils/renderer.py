"""
utils/renderer.py
Renderiza o template HTML do briefing e gera PDF via WeasyPrint.
"""

import base64
import os
from pathlib import Path
from datetime import date
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "components"
LOCALE_MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}


def _data_formatada(d: date) -> str:
    return f"{d.day} de {LOCALE_MESES[d.month]} de {d.year}"


def _enumerate_filter(iterable):
    return enumerate(iterable)


def _subgrupo_css(subgrupo: str) -> str:
    mapa = {
        "capitania": "capitania",
        "motor": "motor",
        "dinâmica": "dinamica",
        "dinamica": "dinamica",
        "eletrônica": "eletronica",
        "eletronica": "eletronica",
        "freio": "freio",
        "aerodinâmica": "aerodinamica",
        "aerodinamica": "aerodinamica",
        "chassi": "chassi",
        "transmissão": "transmissao",
        "transmissao": "transmissao",
        "comunicação": "comunicacao",
        "comunicacao": "comunicacao",
        "calouro": "calouro",
    }
    return mapa.get(subgrupo.lower().strip(), "calouro")


def render_html(briefing_data: dict) -> str:
    """Renderiza o template HTML com os dados do briefing."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters["enumerate"] = _enumerate_filter
    env.filters["zfill"] = lambda s, n: str(s).zfill(n)

    template = env.get_template("briefing_template.html")

    # Processa os passos do procedimento (divide por linha ou por ponto)
    procedimento_raw = briefing_data.get("procedimento", "")
    procedimento_passos = [
        p.strip().lstrip("0123456789.-) ")
        for p in procedimento_raw.split("\n")
        if p.strip() and len(p.strip()) > 3
    ]

    # Imagens de traçado: converte bytes para base64 para embutir no HTML
    tracados_html = []
    for t in briefing_data.get("tracados", []):
        if t.get("bytes"):
            b64 = base64.b64encode(t["bytes"]).decode()
            ext = t.get("ext", "png")
            src = f"data:image/{ext};base64,{b64}"
        else:
            src = t.get("url", "")
        tracados_html.append({"label": t["label"], "src": src})

    # Imagem de setores
    setores_img = ""
    if briefing_data.get("setores_bytes"):
        b64 = base64.b64encode(briefing_data["setores_bytes"]).decode()
        setores_img = f"data:image/png;base64,{b64}"

    ctx = {
        "numero": str(briefing_data.get("numero", "??")).zfill(2),
        "local": briefing_data.get("local", ""),
        "data_formatada": _data_formatada(briefing_data["data"]) if isinstance(briefing_data.get("data"), date) else briefing_data.get("data", ""),
        "pilotos": briefing_data.get("pilotos", []),
        "responsavel": briefing_data.get("responsavel", "Carolina Ferrari"),
        "objetivos_capa": briefing_data.get("objetivos_capa", ""),
        "o_que_buscamos": briefing_data.get("o_que_buscamos", ""),
        "entenda_o_teste": briefing_data.get("entenda_o_teste", ""),
        "kpis": briefing_data.get("kpis", []),
        "cronograma": briefing_data.get("cronograma", []),
        "membros": briefing_data.get("membros", []),
        "tracados": tracados_html,
        "setores_img": setores_img,
        "setores_lista": briefing_data.get("setores_lista", []),
        "procedimento_passos": procedimento_passos,
        "links": briefing_data.get("links", {}),
        "foto_capa": briefing_data.get("foto_capa", ""),
    }

    return template.render(**ctx)


def render_pdf(briefing_data: dict) -> bytes:
    """Gera o PDF do briefing a partir do HTML renderizado."""
    try:
        from weasyprint import HTML, CSS
        html_content = render_html(briefing_data)
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes
    except ImportError:
        raise RuntimeError(
            "WeasyPrint não instalado. Execute: pip install weasyprint"
        )
