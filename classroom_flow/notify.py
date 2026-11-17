"""Notificações push no celular via ntfy (https://ntfy.sh).

Sem servidor próprio e sem dependências: instale o app ntfy (iOS/Android) e
assine o seu tópico. Use um nome de tópico longo e aleatório: em servidores
públicos, quem souber o nome consegue ler e enviar mensagens.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterable

from .config import NTFY_SERVER, NTFY_TOPIC
from .errors import NotifyError


def send(title: str, message: str, *, priority: int = 3,
         tags: Iterable[str] = (), click: str | None = None) -> None:
    if not NTFY_TOPIC:
        raise NotifyError("NTFY_TOPIC não configurado (ambiente ou ~/.config/classroom-flow/env).")
    payload: dict = {"topic": NTFY_TOPIC, "title": title, "message": message,
                     "priority": priority, "tags": list(tags)}
    if click:
        payload["click"] = click                           
    req = urllib.request.Request(
        NTFY_SERVER, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise NotifyError(f"Falha ao enviar notificação: {exc}") from exc
