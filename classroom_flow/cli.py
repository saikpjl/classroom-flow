"""Interface de linha de comando: `cflow <comando>`."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta

import httplib2
from googleapiclient.errors import HttpError

from . import alerts, notify
from .auth import classroom_service, get_credentials
from .classroom import Assignment, find_assignments, get_my_submission, DONE_STATES
from .config import DEFAULT_THRESHOLDS_H
from .errors import (AuthError, ClassroomFlowError, NotFoundError,
                     explain_http_error, is_project_permission_denied)
from .submit import assist_manual, submit_via_api, validate_file

log = logging.getLogger("cflow")


def _fmt(a: Assignment) -> str:
    due = a.due.strftime("%d/%m %H:%M") if a.due else "sem prazo"
    return f"{a.course_name} — {a.title} ({due})"


def _choose(matches: list[Assignment]) -> Assignment:
    if len(matches) == 1:
        return matches[0]
    for i, a in enumerate(matches, 1):
        print(f"  [{i}] {_fmt(a)}")
    if not sys.stdin.isatty():
        raise ClassroomFlowError("Mais de uma atividade encontrada; refine o termo ou use --curso.")
    while True:
        raw = input("Escolha o número (ou Enter para cancelar): ").strip()
        if not raw:
            raise ClassroomFlowError("Cancelado.")
        if raw.isdigit() and 1 <= int(raw) <= len(matches):
            return matches[int(raw) - 1]


def cmd_login(args) -> int:
    get_credentials(interactive=True)
    log.info("✓ Autenticado. Token salvo.")
    return 0


def cmd_entregar(args) -> int:
    path = validate_file(args.arquivo)          # falha cedo, antes de qualquer chamada de rede
    creds = get_credentials()
    service = classroom_service(creds)

    matches = find_assignments(service, args.termo, args.curso)
    if not matches:
        raise NotFoundError(f"Nenhuma atividade com '{args.termo}' nas turmas ativas.")
    assignment = _choose(matches)
    submission = get_my_submission(service, assignment)
    state = submission.get("state", "NEW") if submission else "NEW"

    log.info("Atividade: %s | estado: %s", _fmt(assignment), state)
    if state in DONE_STATES:
        raise ClassroomFlowError("Essa atividade já foi entregue.")

    use_api = (assignment.api_submittable and assignment.work_type == "ASSIGNMENT"
               and submission is not None and not args.manual)

    if args.dry_run:
        log.info("[dry-run] caminho: %s", "API" if use_api else "manual assistido")
        log.info("[dry-run] arquivo: %s", path)
        return 0

    if use_api:
        try:
            submit_via_api(service, creds, assignment, submission, path,
                           turn_in=not args.sem_entregar)
            log.info("✓ Concluído.")
            return 0
        except HttpError as exc:
            if not is_project_permission_denied(exc):
                raise
            log.warning("API recusou (projeto diferente do criador). Indo para o modo manual.")

    elif not assignment.api_submittable:
        log.info("Atividade criada fora deste projeto: a API não permite anexar/entregar.")

    assist_manual(assignment, path)
    return 0


def cmd_prazos(args) -> int:
    service = classroom_service(get_credentials())
    now = datetime.now().astimezone()
    pending = sorted(alerts.collect_pending(service, now, timedelta(days=args.dias),
                                            grace=timedelta(days=7)),
                     key=lambda item: item[0].due)
    if not pending:
        log.info("Nada pendente nos próximos %d dias 🎉", args.dias)
        return 0
    for a, state in pending:
        print(f"{a.due:%d/%m %H:%M}  {alerts.humanize(a.due - now):<18} {a.course_name} — {a.title}")
    return 0


def cmd_monitorar(args) -> int:
    try:
        creds = get_credentials(interactive=False)   # nunca abre navegador (launchd)
    except AuthError as exc:
        alerts.notify_auth_problem(str(exc))
        raise
    service = classroom_service(creds)
    sent = alerts.run_monitor(service, args.limites, dry_run=args.dry_run)
    log.info("Rodada concluída: %d alerta(s).", sent)
    return 0


def cmd_testar(args) -> int:
    notify.send("classroom-flow", "Notificação de teste funcionando ✅", tags=["white_check_mark"])
    log.info("✓ Enviada.")
    return 0

def cmd_lembrete(args) -> int:
    """Lembrete semanal: resumo das pendências + aviso para rodar o cflow."""
    now = datetime.now().astimezone()
    lines = []
    try:
        service = classroom_service(get_credentials(interactive=False))
        pending = sorted(
            alerts.collect_pending(service, now, timedelta(days=3), grace=timedelta(days=3)),
            key=lambda item: item[0].due,
        )
        if pending:
            lines.append(f"{len(pending)} pendência(s):")
            for a, _ in pending[:5]:
                lines.append(f"• {a.due:%d/%m} {a.title}")
            if len(pending) > 5:
                lines.append(f"…e mais {len(pending) - 5}.")
        else:
            lines.append("Nada pendente nos próximos 3 dias 🎉")
    except AuthError:
        lines.append("Seu login expirou: rode `cflow login` no Mac.")
    except (HttpError, ConnectionError, TimeoutError, httplib2.HttpLib2Error) as exc:
        log.warning("Não consegui consultar o Classroom: %s", exc)
        lines.append("Não consegui consultar o Classroom agora.")
    lines.append("Lembrete semanal: abra o terminal e rode `cflow prazos`.")

    message = "\n".join(lines)
    if args.dry_run:
        print(message)
        return 0
    notify.send("Lembrete semanal: classroom-flow", message, priority=3, tags=["calendar"])
    log.info("✓ Lembrete enviado.")
    return 0


def _thresholds(value: str) -> tuple[int, ...]:
    try:
        items = tuple(sorted({int(x) for x in value.split(",") if x.strip()}))
        if not items or min(items) <= 0:
            raise ValueError
        return items
    except ValueError:
        raise argparse.ArgumentTypeError("use horas inteiras positivas separadas por vírgula, ex.: 72,24,6,1")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cflow", description="Entregas e prazos do Google Classroom.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("login", help="autentica via OAuth2 e salva o token")
    s.set_defaults(func=cmd_login)

    s = sub.add_parser("entregar", help="localiza a atividade e entrega o arquivo")
    s.add_argument("termo", help="parte do título da atividade")
    s.add_argument("arquivo", help="caminho do arquivo (PDF, DOCX…)")
    s.add_argument("--curso", help="filtra por parte do nome da turma")
    s.add_argument("--manual", action="store_true", help="força o modo manual assistido")
    s.add_argument("--sem-entregar", action="store_true", help="só anexa, não marca como entregue")
    s.add_argument("--dry-run", action="store_true", help="mostra o plano sem executar")
    s.set_defaults(func=cmd_entregar)

    s = sub.add_parser("prazos", help="lista atividades pendentes")
    s.add_argument("--dias", type=int, default=14)
    s.set_defaults(func=cmd_prazos)

    s = sub.add_parser("monitorar", help="envia alertas de prazo (use no launchd)")
    s.add_argument("--limites", type=_thresholds, default=DEFAULT_THRESHOLDS_H,
                   help="horas de antecedência, ex.: 72,24,6,1")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_monitorar)

    s = sub.add_parser("testar-notificacao", help="envia uma notificação de teste")
    s.set_defaults(func=cmd_testar)


    s = sub.add_parser("lembrete", help="envia o lembrete semanal com resumo das pendências")
    s.add_argument("--dry-run", action="store_true", help="mostra a mensagem sem enviar")
    s.set_defaults(func=cmd_lembrete)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ClassroomFlowError as exc:
        log.error("✗ %s", exc)
    except HttpError as exc:
        log.error("✗ %s", explain_http_error(exc))
    except (ConnectionError, TimeoutError, httplib2.HttpLib2Error) as exc:
        log.error("✗ Sem conexão com a internet: %s", exc)
    except KeyboardInterrupt:
        return 130
    return 1

 


if __name__ == "__main__":
    sys.exit(main())
