"""
utils/renderer.py
Renderiza o template HTML do briefing.
O PDF é gerado pelo próprio navegador via window.print() — sem dependências de sistema.
"""

import base64
from pathlib import Path
from datetime import date
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "components"

LOCALE_MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


def _data_formatada(d) -> str:
    if isinstance(d, date):
        return f"{d.day} de {LOCALE_MESES[d.month]} de {d.year}"
    return str(d)


def _enumerate_filter(iterable):
    return enumerate(iterable)


def render_html(briefing_data: dict) -> str:
    """Renderiza o template HTML com os dados do briefing."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters["enumerate"] = _enumerate_filter
    env.filters["zfill"] = lambda s, n: str(s).zfill(n)

    template = env.get_template("briefing_template.html")

    # Processa passos do procedimento
    procedimento_raw = briefing_data.get("procedimento", "")
    procedimento_passos = [
        p.strip().lstrip("0123456789.-) ")
        for p in procedimento_raw.split("\n")
        if p.strip() and len(p.strip()) > 3
    ]

    # Converte imagens de traçado para base64
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
        "data_formatada": _data_formatada(briefing_data.get("data", "")),
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
    """
    Retorna um PDF real quando o motor WeasyPrint estiver disponível.
    Faz fallback para HTML bytes se a geração de PDF falhar.
    """
    html = render_html(briefing_data)
    try:
        from weasyprint import HTML

        return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
    except Exception:
        return html.encode("utf-8")


def get_pdf_mimetype() -> str:
    return "application/pdf"


def get_pdf_extension() -> str:
    return "pdf"
