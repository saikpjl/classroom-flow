"""Monitoramento de prazos e disparo de alertas (sem duplicar notificações)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Iterator

from . import notify
from .classroom import (DONE_STATES, Assignment, get_my_submission,
                        list_active_courses, list_assignments)
from .config import STATE_FILE
from .errors import NotifyError

log = logging.getLogger(__name__)
STATE_TTL = timedelta(days=60)


def humanize(delta: timedelta) -> str:
    secs = int(delta.total_seconds())
    prefix = "atrasada há " if secs < 0 else "em "
    days, rest = divmod(abs(secs), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        text = f"{days}d {hours}h"
    elif hours:
        text = f"{hours}h {minutes}min"
    else:
        text = f"{minutes}min"
    return prefix + text


def collect_pending(service, now: datetime, horizon: timedelta,
                    grace: timedelta = timedelta(hours=24)) -> Iterator[tuple[Assignment, str]]:
    """Atividades com prazo dentro da janela e ainda NÃO entregues."""
    for course in list_active_courses(service):
        for a in list_assignments(service, course):
            if a.due is None:
                continue
            delta = a.due - now
            if delta > horizon or delta < -grace:
                continue
            sub = get_my_submission(service, a)
            state = sub.get("state", "NEW") if sub else "NEW"
            if state in DONE_STATES:
                continue
            yield a, state


def alert_level(hours_left: float, thresholds: tuple[int, ...]) -> str | None:
    """Menor limite já cruzado (ex.: faltam 20h com limites 72/24/6/1 → '24')."""
    if hours_left < 0:
        return "late"
    crossed = [t for t in thresholds if hours_left <= t]
    return str(min(crossed)) if crossed else None


def build_message(a: Assignment, now: datetime, level: str) -> tuple[str, str, int, list[str]]:
    when = humanize(a.due - now)
    due_txt = a.due.strftime("%d/%m às %H:%M")
    if level == "late":
        return (f"Atrasada: {a.title}", f"{a.course_name}\nVenceu {due_txt}. Entregue o quanto antes.",
                5, ["rotating_light"])
    hours = int(level)
    if hours <= 1:
        priority, tags, hint = 5, ["alarm_clock"], "Envie agora!"
    elif hours <= 6:
        priority, tags, hint = 4, ["warning"], "Finalize e envie o arquivo."
    else:
        priority, tags, hint = 3, ["memo"], "Comece a produzir o arquivo."
    return (f"Prazo {when}: {a.title}",
            f"{a.course_name}\nVence {due_txt}. {hint}", priority, tags)


def _load_state() -> dict[str, str]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, str], now: datetime) -> None:
    fresh = {k: v for k, v in state.items() if now - datetime.fromisoformat(v) < STATE_TTL}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(fresh, indent=2), encoding="utf-8")


def run_monitor(service, thresholds: tuple[int, ...], dry_run: bool = False) -> int:
    """Envia os alertas pendentes e devolve quantos foram disparados."""
    now = datetime.now().astimezone()
    state = _load_state()
    sent = 0
    for a, _ in collect_pending(service, now, horizon=timedelta(hours=max(thresholds))):
        level = alert_level((a.due - now).total_seconds() / 3600, thresholds)
        if level is None:
            continue
        key = f"{a.course_id}:{a.id}:{level}"
        if key in state:
            continue
        title, body, prio, tags = build_message(a, now, level)
        if dry_run:
            log.info("[dry-run] %s | %s", title, body.replace("\n", " · "))
            continue
        try:
            notify.send(title, body, priority=prio, tags=tags, click=a.link or None)
        except NotifyError as exc:
            log.error("%s", exc)  # não marca como enviado: tenta de novo na próxima rodada
            continue
        state[key] = now.isoformat()
        sent += 1
        log.info("🔔 %s", title)
    if not dry_run:
        _save_state(state, now)
    return sent


def notify_auth_problem(message: str) -> None:
    """Avisa (no máximo 1x por dia) que o login precisa ser refeito."""
    now = datetime.now().astimezone()
    state = _load_state()
    key = f"auth_error:{now:%Y-%m-%d}"
    if key in state:
        return
    try:
        notify.send("classroom-flow precisa de login", message, priority=4, tags=["key"])
    except NotifyError as exc:
        log.error("%s", exc)
        return
    state[key] = now.isoformat()
    _save_state(state, now)
