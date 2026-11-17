"""Entrega de atividades: caminho via API e fallback manual assistido.

LIMITAÇÃO DA API DO GOOGLE: modifyAttachments e turnIn só funcionam para
atividades criadas pelo mesmo projeto do Google Cloud (associatedWithDeveloper).
Atividades criadas por professores retornam 403 ProjectPermissionDenied.
Nesse caso, `assist_manual` prepara tudo para você concluir em segundos.
"""
from __future__ import annotations

import logging
import subprocess
import webbrowser
from pathlib import Path

from . import drive
from .classroom import Assignment
from .errors import FileError

log = logging.getLogger(__name__)


def validate_file(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileError(f"Arquivo não encontrado: {path}")
    if not path.is_file():
        raise FileError(f"O caminho não é um arquivo: {path}")
    if path.stat().st_size == 0:
        raise FileError(f"O arquivo está vazio: {path}")
    return path


def submit_via_api(service, creds, assignment: Assignment, submission: dict,
                   path: Path, turn_in: bool = True) -> None:
    """Sobe o arquivo ao Drive, anexa à submissão e (opcional) entrega."""
    log.info("↑ Enviando %s ao Google Drive…", path.name)
    uploaded = drive.upload(creds, path)

    subs = service.courses().courseWork().studentSubmissions()
    ids = dict(courseId=assignment.course_id, courseWorkId=assignment.id, id=submission["id"])

    log.info("📎 Anexando à atividade…")
    subs.modifyAttachments(
        body={"addAttachments": [{"driveFile": {"id": uploaded["id"]}}]}, **ids
    ).execute()

    if turn_in:
        log.info("✅ Marcando como entregue…")
        subs.turnIn(body={}, **ids).execute()


def assist_manual(assignment: Assignment, path: Path) -> None:
    """Revela o arquivo no Finder e abre a atividade no navegador."""
    log.info("Modo manual assistido:")
    log.info("  1) Finder aberto com o arquivo selecionado (arraste-o para a atividade)")
    log.info("  2) Atividade aberta no navegador → 'Adicionar ou criar' → Enviar → 'Entregar'")
    subprocess.run(["open", "-R", str(path)], check=False)
    if assignment.link:
        webbrowser.open(assignment.link)
    else:
        log.warning("A atividade não tem link; abra o Classroom manualmente.")
