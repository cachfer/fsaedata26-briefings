# 🏎 Horeb Briefing Generator
**Fórmula UFMG — Temporada 2026**

Sistema de geração automática de briefings de teste a partir de dados do Notion,
com sugestão de alocação por IA e publicação de páginas web permanentes.

---

## Estrutura do projeto

```
horeb-briefing/
├── app.py                        # App principal Streamlit
├── requirements.txt
├── .env.example                  # Variáveis de ambiente (copiar para .env)
├── .gitignore
├── .streamlit/
│   ├── config.toml               # Tema dark
│   └── secrets.toml.example      # Secrets para deploy (copiar e preencher)
├── services/
│   ├── notion_service.py         # Leitura do Notion
│   ├── drive_service.py          # Google Drive (traçados + briefings)
│   └── ai_service.py             # Anthropic API (alocação + textos)
├── components/
│   └── briefing_template.html    # Template HTML/CSS do briefing
└── utils/
    └── renderer.py               # Renderização HTML → PDF
```

---

## Setup local (primeira vez)

### 1. Clone o repositório e instale dependências

```bash
git clone https://github.com/cachfer/fsaedata26-briefings
cd fsaedata26-briefings
pip install -r requirements.txt
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite o .env com suas credenciais
```

### 3. Configure a integração com o Notion

1. Acesse [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Clique em **New integration** → dê o nome "Horeb Briefing"
3. Copie o **Internal Integration Token** → cole em `NOTION_TOKEN` no `.env`
4. Abra cada database no Notion (Testes, Metodologias, formulários de comparecimento)
5. Clique em `...` (canto superior direito) → **Add connections** → selecione "Horeb Briefing"
6. Copie o ID de cada database da URL (os 32 caracteres após a última `/` e antes de `?`) → cole nas variáveis correspondentes no `.env`

### 4. Configure o Google Drive

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto → ative a **Google Drive API**
3. Em **Credentials** → **Create credentials** → **Service account**
4. Baixe o arquivo JSON → salve como `credentials.json` na raiz do projeto
5. Copie o `client_email` da service account
6. Na pasta de Traçados e na pasta de Briefings do Drive, clique em **Share** e adicione o `client_email` como editor
7. Copie os IDs das pastas da URL do Drive → cole em `DRIVE_TRACADOS_FOLDER_ID` e `DRIVE_BRIEFINGS_FOLDER_ID`

### 5. Configure a API da Anthropic

1. Acesse [console.anthropic.com](https://console.anthropic.com)
2. Crie uma API key → cole em `ANTHROPIC_API_KEY` no `.env`

### 6. Rode localmente

```bash
streamlit run app.py
```

---

## Deploy no Streamlit Cloud

1. Suba o projeto para um repositório **privado** no GitHub
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/SEU_USUARIO/horeb-briefing.git
   git push -u origin main
   ```

2. Acesse [share.streamlit.io](https://share.streamlit.io) → **New app**

3. Selecione o repositório e o arquivo `app.py`

4. Em **Advanced settings → Secrets**, cole o conteúdo do `.streamlit/secrets.toml.example`
   preenchido com suas credenciais reais

5. Clique em **Deploy** — a URL será algo como `https://horeb-briefing.streamlit.app`

6. Atualize `APP_URL` nos secrets com a URL real

---

## Convenção de nomes para imagens de traçado no Drive

As imagens devem estar em subpastas com o nome do local:

```
Traçados/
├── rbc/
│   ├── tracado_C_montagem.png
│   ├── tracado_C_setores.png
│   ├── tracado_enduro_montagem.png
│   └── tracado_enduro_setores.png
└── expominas/
    ├── skidpad_montagem.png
    ├── hairpin_montagem.png
    └── setores.png
```

Arquivos com `montagem` no nome → aparecem como "Montagem do Traçado"
Arquivos com `setor` no nome → aparecem como "Divisão de Setores"

---

## Fluxo de uso (dia do teste)

1. Abra `https://horeb-briefing.streamlit.app`
2. Faça login com a senha da equipe
3. Selecione a data do teste no dropdown
4. Clique em **Carregar dados do Notion**
5. Confirme número do teste, local, circuito
6. Selecione os pilotos do dia
7. Clique em **Gerar sugestão de alocação com IA** e revise/edite a tabela
8. Ajuste o cronograma se necessário
9. Clique em **Gerar seções com IA** para preencher os textos
10. Selecione as imagens de traçado
11. Preencha os links se não estiverem configurados
12. Clique em **Publicar** → copie o link → mande no grupo da equipe

---

## Variáveis de ambiente — referência completa

| Variável | Descrição |
|---|---|
| `NOTION_TOKEN` | Token de integração do Notion |
| `NOTION_TESTES_DB_ID` | ID do banco de dados de Testes |
| `NOTION_METODOLOGIAS_DB_ID` | ID do banco de dados de Metodologias |
| `COMPARECIMENTO_RBC_SEG` | ID do formulário RBC segunda-feira |
| `COMPARECIMENTO_RBC_TER` | ID do formulário RBC terça-feira |
| ... | (idem para outros dias/locais) |
| `DRIVE_TRACADOS_FOLDER_ID` | ID da pasta de Traçados no Drive |
| `DRIVE_BRIEFINGS_FOLDER_ID` | ID da pasta de Briefings no Drive |
| `ANTHROPIC_API_KEY` | Chave da API Anthropic |
| `ADMIN_PASSWORD` | Senha de acesso ao painel admin |
| `APP_URL` | URL pública do app (após deploy) |
| `LINK_PASTA_LOGS` | Link fixo para a pasta de logs |
| `LINK_FMEA` | Link fixo para o formulário FMEA |
| `LINK_FEEDBACK` | Link fixo para o formulário de feedback |
| `LINK_TEMPO_VOLTA` | Link fixo para a planilha de tempo de volta |
| `LINK_GRUPO_TEMPO` | Link do grupo WhatsApp de tempo |
| `LINK_GRUPO_CONE` | Link do grupo WhatsApp de cone |
