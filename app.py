"""
app.py
App principal Streamlit — Fórmula SAE UFMG Briefing Generator
Interface admin para criação/publicação e visualização pública dos briefings.
"""

import streamlit as st
import os
import json
import pandas as pd
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

# ── Lê secrets do Streamlit Cloud se disponíveis, senão usa .env ────────────
def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(key, default)


# ── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Briefing | Fórmula SAE UFMG",
    page_icon="🏎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS global ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800;900&family=Barlow:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Barlow', sans-serif; }
.stApp { background-color: #0a0a0a; color: #ffffff; }
h1, h2, h3 {
    font-family: 'Barlow Condensed', sans-serif !important;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}
[data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #333; }
.stButton > button[kind="primary"] {
    background-color: #cc0000 !important;
    border: none !important;
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
.stButton > button[kind="secondary"] {
    background-color: transparent !important;
    border: 1px solid #444 !important;
    color: #aaa !important;
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
.briefing-card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-left: 4px solid #cc0000;
    padding: 1rem 1.5rem;
    margin-bottom: 0.8rem;
}
.briefing-card-num {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 1.8rem;
    color: white;
    line-height: 1;
}
.briefing-card-info { font-size: 0.85rem; color: #888; margin-top: 0.2rem; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# FUNÇÕES — definidas antes do roteamento
# ════════════════════════════════════════════════════════════════════════════

def _show_public_briefing(file_id: str):
    """Renderiza um briefing publicado a partir do Drive."""
    from services.drive_service import load_briefing
    from utils.renderer import render_html

    with st.spinner("Carregando briefing..."):
        data = load_briefing(file_id)

    if not data:
        st.error("Briefing não encontrado.")
        return

    if isinstance(data.get("data"), str):
        try:
            data["data"] = date.fromisoformat(data["data"])
        except ValueError:
            pass

    html = render_html(data)
    st.components.v1.html(html, height=12000, scrolling=True)

    col1, col2, col3 = st.columns([3, 1, 3])
    with col2:
        num = str(data.get("numero", "XX")).zfill(2)
        st.download_button(
            label="📄 Baixar para impressão (HTML)",
            data=html.encode("utf-8"),
            file_name=f"briefing_T{num}_{data.get('data', '')}.html",
            mime="text/html",
        )


def _show_historico():
    """Página pública com todos os briefings publicados."""
    from services.drive_service import list_briefings

    st.markdown("## 📋 Histórico de Briefings")
    st.markdown("**Fórmula SAE UFMG — Temporada 2026**")

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("← Voltar"):
            st.query_params.clear()
            st.rerun()

    st.divider()

    with st.spinner("Carregando histórico..."):
        try:
            briefings = list_briefings()
        except Exception as e:
            st.error(f"Erro ao acessar o Drive: {e}")
            return

    if not briefings:
        st.info("Nenhum briefing publicado ainda.")
        return

    for b in briefings:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"""
            <div class="briefing-card">
                <div class="briefing-card-num">#{str(b['numero']).zfill(2)}</div>
                <div class="briefing-card-info">{b['data']} · {b.get('local', '')}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("Ver", key=f"ver_{b['file_id']}"):
                st.query_params["b"] = b["file_id"]
                st.rerun()


def _show_admin():
    """Interface admin com autenticação."""
    ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD", "horeb2026")

    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown("### 🏎 Fórmula SAE UFMG — Briefing Generator")
        st.markdown("**Área Administrativa**")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary"):
            if senha == ADMIN_PASSWORD:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
        st.markdown("---")
        if st.button("📋 Ver histórico público"):
            st.query_params["page"] = "historico"
            st.rerun()
        return

    _admin_panel()


def _admin_panel():
    """Painel principal do admin."""
    from services.drive_service import list_tracados, download_tracado
    from services.ai_service import suggest_task_allocation, generate_briefing_sections, generate_schedule

    st.markdown("# 🏎 Fórmula SAE UFMG — Briefing Generator")

    col_nav1, col_nav2, col_nav3 = st.columns([2, 2, 6])
    with col_nav1:
        if st.button("📋 Histórico"):
            st.query_params["page"] = "historico"
            st.rerun()
    with col_nav2:
        if st.button("🚪 Sair"):
            st.session_state.autenticado = False
            st.rerun()

    st.divider()

    # ── Modo de entrada ──────────────────────────────────────────────────────
    modo = st.radio("Fonte de dados", ["Notion", "Manual"], horizontal=True, key="modo_fonte")
    if st.session_state.get("_ultimo_modo") != modo:
        st.session_state._ultimo_modo = modo
        st.session_state.briefing_data = None
        st.session_state.membros_raw = []
        st.session_state.membros_editados = None
        st.session_state.cronograma_editado = None
        st.session_state.secoes_geradas = None
        st.session_state.tracados_selecionados = []
        st.session_state.data_selecionada = None
        st.session_state.publish_html_bytes = None

    st.divider()

    # ── 1. Seleção de data / carregamento ────────────────────────────────────
    st.markdown("### 1. Selecione a data do teste")

    from datetime import date as date_type
    hoje = date_type.today()

    if modo == "Notion":
        from services.notion_service import (
            get_test_dates, get_test_by_date,
            get_validacoes_do_teste, get_membros_confirmados,
        )

        with st.spinner("Buscando testes no Notion..."):
            try:
                datas = get_test_dates()
            except Exception as e:
                st.error(f"Erro ao conectar ao Notion: {e}")
                st.info("Verifique NOTION_TOKEN e NOTION_TESTES_DB_ID nos secrets.")
                return

        if not datas:
            st.warning("Nenhum teste encontrado no Notion.")
            return

        default_date = hoje if hoje in datas else min((d for d in datas if d >= hoje), default=datas[-1])
        data_escolhida = st.date_input(
            "Data do teste",
            value=default_date,
            min_value=min(datas),
            max_value=max(datas),
            format="DD/MM/YYYY",
        )
        if data_escolhida not in datas:
            st.warning("Não há teste cadastrado no Notion para esta data.")
            return

        if st.session_state.get("data_selecionada") != data_escolhida:
            st.session_state.data_selecionada = data_escolhida
            st.session_state.briefing_data = None
            st.session_state.membros_raw = []
            st.session_state.membros_editados = None
            st.session_state.cronograma_editado = None
            st.session_state.secoes_geradas = None
            st.session_state.tracados_selecionados = []
            st.session_state.publish_html_bytes = None

        if st.button("📥 Carregar dados do Notion", type="primary"):
            with st.spinner("Carregando dados..."):
                try:
                    st.caption("1/3 Buscando teste selecionado no Notion...")
                    teste = get_test_by_date(data_escolhida)
                    if not teste:
                        st.error("Teste não encontrado para esta data no Notion.")
                        st.stop()

                    st.caption("2/3 Carregando validações da metodologia...")
                    validacoes = get_validacoes_do_teste(teste.get("validacao_ids", []))

                    st.caption("3/3 Carregando membros confirmados...")
                    membros = get_membros_confirmados(teste.get("local", ""), data_escolhida)
                except Exception as e:
                    st.error(f"Erro ao carregar dados do Notion: {e}")
                    st.info("Se isso acontece para todo mundo, confira o token do Notion, os IDs dos databases e o nome das colunas usadas nas queries.")
                    st.stop()

            st.session_state.briefing_data = {**teste, "validacoes": validacoes}
            st.session_state.membros_raw = membros
            st.session_state.membros_editados = None
            st.session_state.cronograma_editado = None
            st.session_state.secoes_geradas = None
            st.success(
                f"✅ Teste #{teste['numero']} carregado — "
                f"{len(membros)} membros confirmados, {len(validacoes)} validações."
            )
            st.rerun()

    else:  # Manual
        data_escolhida = st.date_input(
            "Data do teste",
            value=st.session_state.get("data_selecionada") or hoje,
            format="DD/MM/YYYY",
        )

        if st.session_state.get("data_selecionada") != data_escolhida:
            st.session_state.data_selecionada = data_escolhida
            st.session_state.briefing_data = {
                "numero": "",
                "local": "",
                "responsavel": "Carolina Ferrari",
                "circuito": "",
                "objetivos_capa": "",
                "pilotos": [],
                "validacoes": [],
                "data": data_escolhida,
            }
            st.session_state.membros_raw = []
            st.session_state.membros_editados = None
            st.session_state.cronograma_editado = None
            st.session_state.secoes_geradas = None
            st.session_state.tracados_selecionados = []
            st.session_state.publish_html_bytes = None

        if not st.session_state.get("briefing_data"):
            st.session_state.briefing_data = {
                "numero": "",
                "local": "",
                "responsavel": "Carolina Ferrari",
                "circuito": "",
                "objetivos_capa": "",
                "pilotos": [],
                "validacoes": [],
                "data": data_escolhida,
            }

    if not st.session_state.get("briefing_data"):
        return

    bd = st.session_state.briefing_data
    validacoes = bd.get("validacoes", [])

    # ── 2. Informações gerais ────────────────────────────────────────────────
    st.divider()
    st.markdown("### 2. Informações gerais")
    col1, col2 = st.columns(2)
    with col1:
        bd["numero"] = st.text_input("Número do teste", value=str(bd.get("numero", "")))
        bd["local"] = st.text_input("Local", value=bd.get("local", ""))
    with col2:
        bd["responsavel"] = st.text_input("Responsável", value=bd.get("responsavel", "Carolina Ferrari"))
        CIRCUITOS_DISPONIVEIS = ["A", "B", "C", "D", "E", "Enduro", "Livre", "SkidPad", "Hairpin", "Autocross"]
        circuito_atual = bd.get("circuito", "")
        if circuito_atual and circuito_atual not in CIRCUITOS_DISPONIVEIS:
            CIRCUITOS_DISPONIVEIS = [circuito_atual] + CIRCUITOS_DISPONIVEIS
        idx = CIRCUITOS_DISPONIVEIS.index(circuito_atual) if circuito_atual in CIRCUITOS_DISPONIVEIS else 0
        bd["circuito"] = st.selectbox("Circuito", options=CIRCUITOS_DISPONIVEIS, index=idx)

    bd["objetivos_capa"] = st.text_area(
        "Objetivos (resumo para a capa)",
        value=bd.get("objetivos_capa") or ", ".join(v["nome"] for v in validacoes),
        height=80,
    )

    # ── 3. Pilotos ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 3. Pilotos")
    membros_raw = st.session_state.get("membros_raw", [])
    PILOTOS_FIXOS = ["João Gabriel", "Gustavo Fornazier", "Milione", "Juan", "Raphael"]
    bd["pilotos"] = st.multiselect(
        "Selecione os pilotos do dia",
        options=PILOTOS_FIXOS,
        default=[p for p in bd.get("pilotos", []) if p in PILOTOS_FIXOS],
    )

    # ── 4. Divisão de tarefas ────────────────────────────────────────────────
    st.divider()
    st.markdown("### 4. Divisão de tarefas")

    if modo == "Manual":
        from services.notion_service import get_membros_confirmados
        if st.button("📥 Carregar membros do Notion", type="secondary"):
            local_atual = bd.get("local", "")
            if not local_atual:
                st.warning("Preencha o local na seção 2 antes de carregar os membros.")
            else:
                with st.spinner("Carregando membros..."):
                    try:
                        membros = get_membros_confirmados(local_atual, data_escolhida)
                        st.session_state.membros_raw = membros
                        st.session_state.membros_editados = [m.copy() for m in membros]
                        if membros:
                            st.success(f"✅ {len(membros)} membros confirmados carregados.")
                        else:
                            st.warning("Nenhum membro encontrado. Verifique se o local está correto e se há respostas no formulário.")
                    except Exception as e:
                        st.error(f"Erro ao carregar membros do Notion: {e}")

    if st.button("🤖 Gerar sugestão de alocação com IA"):
        with st.spinner("A IA está alocando tarefas..."):
            try:
                membros_alocados = suggest_task_allocation(
                    membros=[m.copy() for m in membros_raw],
                    validacoes=validacoes,
                    pilotos_escolhidos=bd["pilotos"],
                    local=bd["local"],
                    circuito=bd["circuito"],
                )
                st.session_state.membros_editados = membros_alocados
                st.success("Sugestão gerada! Edite a tabela abaixo conforme necessário.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro na IA de alocação: {e}")

    if st.session_state.membros_editados is None:
        st.session_state.membros_editados = [m.copy() for m in membros_raw]

    membros_df = pd.DataFrame([
        {
            "Nome": m["nome"],
            "Subgrupo": m["subgrupo"],
            "Tarefa Box": m.get("tarefa_box", ""),
            "Tarefa Pista": m.get("tarefa_pista", ""),
            "Chegada": m.get("chegada", ""),
        }
        for m in st.session_state.membros_editados
    ])

    edited_df = st.data_editor(
        membros_df,
        use_container_width=True,
        num_rows="dynamic",
        key="membros_editor",
    )

    def _is_piloto(nome_membro: str, pilotos: list[str]) -> bool:
        if not nome_membro:
            return False
        nome_lower = nome_membro.lower()
        for p in pilotos:
            p_lower = p.lower()
            if p_lower in nome_lower or nome_lower in p_lower:
                return True
            for palavra in p_lower.split():
                if len(palavra) > 3 and palavra in nome_lower:
                    return True
        return False

    # Preserva Carro/Saída (campos ocultos) ao sincronizar edições
    _prev_membros = {
        m["nome"]: m
        for m in st.session_state.membros_editados
        if m.get("nome")
    }
    st.session_state.membros_editados = [
        {
            "nome": row["Nome"],
            "subgrupo": row["Subgrupo"],
            "tem_carro": _prev_membros.get(row["Nome"] or "", {}).get("tem_carro", False),
            "tarefa_box": row["Tarefa Box"],
            "tarefa_pista": row["Tarefa Pista"],
            "chegada": row["Chegada"],
            "saida": _prev_membros.get(row["Nome"] or "", {}).get("saida", ""),
            "piloto": _is_piloto(row["Nome"], bd.get("pilotos", [])),
        }
        for _, row in edited_df.iterrows()
    ]

    # ── 5. Cronograma ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 5. Cronograma")
    num_pilotos = max(len(bd.get("pilotos", [])), 1)

    if st.button("⚙️ Gerar cronograma automático"):
        st.session_state.cronograma_editado = generate_schedule(bd["local"], validacoes, num_pilotos)
        st.rerun()

    if st.session_state.cronograma_editado is None:
        if modo == "Notion" or bd.get("local"):
            st.session_state.cronograma_editado = generate_schedule(bd["local"], validacoes, num_pilotos)
        else:
            st.session_state.cronograma_editado = [{"atividade": "", "horario": "", "comentario": ""}]
            st.caption("Preencha o local na seção 2 e clique em 'Gerar cronograma automático'.")

    crono_df = pd.DataFrame(st.session_state.cronograma_editado)
    edited_crono = st.data_editor(
        crono_df,
        use_container_width=True,
        num_rows="dynamic",
        key="crono_editor",
    )
    st.session_state.cronograma_editado = edited_crono.to_dict("records")

    # ── 6. Seções textuais ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### 6. Seções textuais")

    s = st.session_state.secoes_geradas or {}

    if modo == "Notion":
        if st.button("✍️ Gerar seções com IA (objetivos / revisão teórica / procedimento)"):
            with st.spinner("Gerando conteúdo com IA..."):
                try:
                    secoes = generate_briefing_sections(validacoes)
                    st.session_state.secoes_geradas = secoes
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro na IA de seções: {e}")

        bd["o_que_buscamos"] = st.text_area(
            "O que buscamos atingir",
            value=bd.get("o_que_buscamos") or s.get("o_que_buscamos", ""),
            height=200,
        )
        bd["entenda_o_teste"] = st.text_area(
            "Entenda o teste",
            value=bd.get("entenda_o_teste") or s.get("entenda_o_teste", ""),
            height=200,
        )
    else:
        bd["o_que_buscamos"] = ""
        bd["entenda_o_teste"] = ""

    bd["procedimento"] = st.text_area(
        "Procedimento em pista",
        value=bd.get("procedimento") or s.get("procedimento", ""),
        height=200,
    )
    kpis_raw = st.text_input(
        "KPIs (separados por vírgula)",
        value=", ".join(bd.get("kpis", [])),
    )
    bd["kpis"] = [k.strip() for k in kpis_raw.split(",") if k.strip()]

    # ── 7. Traçado e setores ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 7. Traçado e setores")

    with st.spinner("Buscando imagens no Drive..."):
        try:
            tracados_disponiveis = list_tracados(bd["local"])
        except Exception as e:
            st.warning(f"Não foi possível acessar o Drive: {e}")
            tracados_disponiveis = []

    if tracados_disponiveis:
        nomes_tracados = [t["name"] for t in tracados_disponiveis]

        # Seleção automática baseada no circuito escolhido
        circuito_lower = bd.get("circuito", "").lower().strip()
        auto_selecionados = []
        if circuito_lower:
            for nome in nomes_tracados:
                nome_lower = nome.lower()
                # Casa com padrão: tracado_C_montagem, tracado_C_setores, etc.
                if circuito_lower in nome_lower or f"_{circuito_lower}_" in nome_lower or nome_lower.startswith(circuito_lower):
                    auto_selecionados.append(nome)

        default_selecionados = auto_selecionados or [
            n for n in st.session_state.tracados_selecionados
            if n in nomes_tracados
        ]

        if auto_selecionados:
            st.caption(f"✅ {len(auto_selecionados)} imagem(ns) selecionada(s) automaticamente para o circuito **{bd['circuito']}**")

        selecionados = st.multiselect(
            "Imagens de traçado/setores",
            options=nomes_tracados,
            default=default_selecionados,
        )
        st.session_state.tracados_selecionados = selecionados

        tracados_com_bytes = []
        for nome in selecionados:
            t = next(x for x in tracados_disponiveis if x["name"] == nome)
            label = (
                "Montagem do Traçado" if t["tipo"] == "montagem"
                else "Divisão de Setores" if t["tipo"] == "setores"
                else nome
            )
            try:
                img_bytes = download_tracado(t["id"])
            except Exception:
                img_bytes = b""
            ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else "png"
            tracados_com_bytes.append({
                "label": label,
                "bytes": img_bytes,
                "ext": ext,
                "tipo": t["tipo"],
            })

        bd["tracados"] = [t for t in tracados_com_bytes if t["tipo"] in ("montagem", "outro")]
        setores_imgs = [t for t in tracados_com_bytes if t["tipo"] == "setores"]
        bd["setores_bytes"] = setores_imgs[0]["bytes"] if setores_imgs else b""
    else:
        st.info("Nenhuma imagem encontrada no Drive para este local.")
        bd["tracados"] = []
        bd["setores_bytes"] = b""

    setores_texto = st.text_area(
        "Descrição dos setores (um por linha, ex: 'Reta principal')",
        value="\n".join(bd.get("setores_lista", [])),
        height=120,
    )
    bd["setores_lista"] = [l.strip() for l in setores_texto.split("\n") if l.strip()]


    # ── 8. Links úteis (fixos — configurados nos secrets) ────────────────────
    bd["links"] = {
        "pasta_logs": _get_secret("LINK_PASTA_LOGS"),
        "fmea":        _get_secret("LINK_FMEA"),
        "feedback":    _get_secret("LINK_FEEDBACK"),
        "tempo_volta": _get_secret("LINK_TEMPO_VOLTA"),
        "grupo_tempo": _get_secret("LINK_GRUPO_TEMPO"),
        "grupo_cone":  _get_secret("LINK_GRUPO_CONE"),
    }

    # ── 9. Publicar ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 9. Publicar")

    def _build_full_briefing() -> dict:
        """Monta o dict completo com todos os dados editados."""
        return {
            **bd,
            "membros": st.session_state.membros_editados,
            "cronograma": st.session_state.cronograma_editado,
        }

    col_prev, col_pub = st.columns(2)
    with col_prev:
        preview_btn = st.button("👁 Preview", type="secondary", use_container_width=True)
    with col_pub:
        publish_btn = st.button("🚀 Publicar briefing", type="primary", use_container_width=True)

    if preview_btn:
        from utils.renderer import render_html
        full_preview = _build_full_briefing()
        with st.spinner("Gerando preview..."):
            try:
                st.session_state.preview_html = render_html(full_preview)
                st.session_state.preview_ready = True
            except Exception as e:
                st.error(f"Erro ao gerar preview: {e}")

    if publish_btn:
        full = _build_full_briefing()
        from utils.renderer import render_html
        num = str(full.get("numero", "XX")).zfill(2)
        with st.spinner("Gerando briefing..."):
            st.session_state.publish_html_bytes = render_html(full).encode("utf-8")
            st.session_state.publish_num = num
            st.session_state.publish_data = str(data_escolhida)
        st.success("Briefing gerado!")

    if st.session_state.get("publish_html_bytes"):
        num_pub = st.session_state.publish_num
        data_pub = st.session_state.publish_data
        st.markdown("Baixe o arquivo, abra no navegador e use **Ctrl+P** (ou menu de compartilhamento no celular) para imprimir como PDF.")
        st.download_button(
            label="⬇ Baixar briefing",
            data=st.session_state.publish_html_bytes,
            file_name=f"briefing_T{num_pub}_{data_pub}.html",
            mime="text/html",
            use_container_width=True,
        )
        manual_link = st.text_input(
            "Link do Drive após upload manual",
            value=st.session_state.get("manual_drive_link", ""),
            placeholder="Cole aqui o link do arquivo no Drive",
        )
        if manual_link:
            st.session_state.manual_drive_link = manual_link
            st.markdown("**Link para compartilhar no grupo:**")
            st.code(manual_link)
            st.markdown(f"[Abrir briefing ↗]({manual_link})")

    if st.session_state.get("preview_ready") and st.session_state.get("preview_html"):
        st.caption("Preview temporário, sem salvar no Drive.")
        st.components.v1.html(st.session_state.preview_html, height=12000, scrolling=True)
        st.download_button(
            label="📄 Baixar HTML do preview",
            data=st.session_state.preview_html.encode("utf-8"),
            file_name="briefing_preview.html",
            mime="text/html",
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# ROTEAMENTO — após todas as funções estarem definidas
# ════════════════════════════════════════════════════════════════════════════

params = st.query_params

if "b" in params:
    _show_public_briefing(params["b"])
elif params.get("page") == "historico":
    _show_historico()
else:
    _show_admin()