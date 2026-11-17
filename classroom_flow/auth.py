"""Autenticação OAuth2 (fluxo "Desktop app") com cache e renovação do token."""
from __future__ import annotations

import json
import logging
import os

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import APP_DIR, CREDENTIALS_FILE, SCOPES, TOKEN_FILE
from .errors import AuthError

log = logging.getLogger(__name__)


def _save_token(creds: Credentials) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(TOKEN_FILE, 0o600)  # só o seu usuário lê


def _load_token() -> Credentials | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except (ValueError, json.JSONDecodeError):
        log.warning("token.json corrompido; será recriado.")
        TOKEN_FILE.unlink(missing_ok=True)
        return None


def get_credentials(interactive: bool = True) -> Credentials:
    """Retorna credenciais válidas, renovando ou refazendo o login se preciso.

    interactive=False (usado pelo launchd) nunca abre o navegador: levanta
    AuthError para que o chamador possa avisar você.
    """
    creds = _load_token()
    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except RefreshError:
            # Token revogado, escopos mudaram, ou expirou (apps em modo "Testing"
            # têm refresh token válido por apenas 7 dias).
            log.warning("Token expirado ou revogado; novo login necessário.")
            TOKEN_FILE.unlink(missing_ok=True)
        except TransportError as exc:
            raise AuthError(f"Sem conexão para renovar o token: {exc}") from exc

    if not interactive:
        raise AuthError("Login necessário. Rode `cflow login` no terminal.")

    if not CREDENTIALS_FILE.exists():
        raise AuthError(
            f"Arquivo de credenciais não encontrado: {CREDENTIALS_FILE}\n"
            "Baixe o JSON do cliente OAuth (Desktop app) no Google Cloud e salve nesse caminho."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    _save_token(creds)
    return creds


def classroom_service(creds: Credentials):
    return build("classroom", "v1", credentials=creds, cache_discovery=False)
