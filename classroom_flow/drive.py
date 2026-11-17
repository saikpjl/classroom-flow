"""Upload de arquivos para o Google Drive (necessário para anexar via API)."""
from __future__ import annotations

import mimetypes
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload(creds, path: Path) -> dict:
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    media = MediaFileUpload(str(path), mimetype=mime, resumable=True)
    return drive.files().create(
        body={"name": path.name}, media_body=media, fields="id,name,webViewLink"
    ).execute()
