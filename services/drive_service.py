"""
services/drive_service.py
Leitura de imagens de traçado e persistência dos briefings publicados.
"""

import os
import io
import json
from datetime import date, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

TRACADOS_FOLDER_ID = os.environ.get("DRIVE_TRACADOS_FOLDER_ID", "")
BRIEFINGS_FOLDER_ID = os.environ.get("DRIVE_BRIEFINGS_FOLDER_ID", "")


def _get_service():
    """
    Cria e retorna o cliente autenticado do Google Drive.
    Suporta st.secrets["GOOGLE_CREDENTIALS"] (Streamlit Cloud)
    ou arquivo credentials.json local (desenvolvimento).
    """
    try:
        import streamlit as st
        creds_info = dict(st.secrets["GOOGLE_CREDENTIALS"])
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
    except Exception:
        creds_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON", "credentials.json")
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )
    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Traçados
# ---------------------------------------------------------------------------

def list_tracados(local: str) -> list[dict]:
    """
    Lista as imagens de traçado disponíveis para um local.
    Espera pastas com nome do local dentro de TRACADOS_FOLDER_ID.
    Retorna lista de dicts com id, name, tipo (montagem|setores).
    """
    service = _get_service()

    # Encontra a subpasta do local
    local_normalizado = local.lower().replace(" ", "_")
    query = (
        f"'{TRACADOS_FOLDER_ID}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    folders = service.files().list(q=query, fields="files(id, name)").execute()["files"]

    pasta_local = None
    for f in folders:
        if local_normalizado in f["name"].lower() or f["name"].lower() in local_normalizado:
            pasta_local = f
            break

    if not pasta_local:
        return []

    # Lista imagens dentro da pasta
    query_imgs = (
        f"'{pasta_local['id']}' in parents "
        f"and mimeType contains 'image/' "
        f"and trashed = false"
    )
    imgs = service.files().list(
        q=query_imgs, fields="files(id, name, webContentLink)"
    ).execute()["files"]

    result = []
    for img in imgs:
        nome = img["name"].lower()
        tipo = "montagem" if "montagem" in nome else ("setores" if "setor" in nome else "outro")
        result.append({
            "id": img["id"],
            "name": img["name"],
            "tipo": tipo,
        })

    return sorted(result, key=lambda x: x["name"])


def download_tracado(file_id: str) -> bytes:
    """Baixa uma imagem de traçado pelo ID e retorna os bytes."""
    service = _get_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Briefings persistidos
# ---------------------------------------------------------------------------

def save_briefing(briefing_data: dict) -> str:
    """
    Salva um briefing como JSON na pasta briefings do Drive.
    Retorna o file_id do arquivo criado/atualizado.
    """
    service = _get_service()
    test_date = briefing_data.get("data", "")
    test_num = briefing_data.get("numero", "XX")
    filename = f"briefing_T{str(test_num).zfill(2)}_{test_date}.json"

    content = json.dumps(briefing_data, ensure_ascii=False, indent=2, default=str)
    buf = io.BytesIO(content.encode("utf-8"))

    # Verifica se já existe um arquivo com esse nome
    query = (
        f"'{BRIEFINGS_FOLDER_ID}' in parents "
        f"and name = '{filename}' "
        f"and trashed = false"
    )
    existing = service.files().list(q=query, fields="files(id)").execute()["files"]

    if existing:
        # Atualiza
        file_id = existing[0]["id"]
        service.files().update(
            fileId=file_id,
            media_body=MediaIoBaseUpload(buf, mimetype="application/json"),
        ).execute()
    else:
        # Cria novo
        metadata = {"name": filename, "parents": [BRIEFINGS_FOLDER_ID]}
        file = service.files().create(
            body=metadata,
            media_body=MediaIoBaseUpload(buf, mimetype="application/json"),
            fields="id",
        ).execute()
        file_id = file["id"]

    return file_id


def list_briefings() -> list[dict]:
    """
    Lista todos os briefings publicados na pasta briefings,
    ordenados por data decrescente.
    """
    service = _get_service()
    query = (
        f"'{BRIEFINGS_FOLDER_ID}' in parents "
        f"and mimeType = 'application/json' "
        f"and trashed = false"
    )
    files = service.files().list(
        q=query,
        fields="files(id, name, createdTime)",
        orderBy="createdTime desc",
    ).execute()["files"]

    result = []
    for f in files:
        # Extrai número e data do nome: briefing_T05_2026-05-19.json
        parts = f["name"].replace(".json", "").split("_")
        numero = parts[1].replace("T", "") if len(parts) > 1 else "?"
        data_str = parts[2] if len(parts) > 2 else ""
        result.append({
            "file_id": f["id"],
            "filename": f["name"],
            "numero": numero,
            "data": data_str,
        })

    return result


def load_briefing(file_id: str) -> dict | None:
    """Carrega um briefing publicado pelo file_id do Drive."""
    try:
        service = _get_service()
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return json.loads(buf.getvalue().decode("utf-8"))
    except Exception:
        return None
