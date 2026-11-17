"""Configuração central: caminhos, escopos OAuth e variáveis de ambiente.

Variáveis podem vir do ambiente ou do arquivo ~/.config/classroom-flow/env
(linhas KEY=VALUE). O arquivo é útil porque o launchd não lê o ~/.zshrc.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(os.environ.get("CLASSROOM_FLOW_HOME", Path.home() / ".config" / "classroom-flow"))
CREDENTIALS_FILE = APP_DIR / "credentials.json"  # baixado do Google Cloud
TOKEN_FILE = APP_DIR / "token.json"              # gerado após o login
STATE_FILE = APP_DIR / "alert_state.json"        # evita notificações repetidas
ENV_FILE = APP_DIR / "env"

# Escopos mínimos necessários.
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file(ENV_FILE)

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# Antecedências (em horas) em que você será avisado.
DEFAULT_THRESHOLDS_H = (72, 24, 6, 1)
