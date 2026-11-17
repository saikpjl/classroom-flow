"""Exceções do projeto e tradução de erros HTTP da API em mensagens úteis."""
from __future__ import annotations

from googleapiclient.errors import HttpError


class ClassroomFlowError(Exception):
    """Erro esperado, com mensagem pronta para o usuário."""


class AuthError(ClassroomFlowError):
    pass


class NotFoundError(ClassroomFlowError):
    pass


class FileError(ClassroomFlowError):
    pass


class NotifyError(ClassroomFlowError):
    pass


def is_project_permission_denied(err: HttpError) -> bool:
    return "ProjectPermissionDenied" in str(err) or (
        getattr(err.resp, "status", None) == 403 and "Developer Console" in str(err)
    )


def explain_http_error(err: HttpError) -> str:
    status = getattr(err.resp, "status", None)
    if is_project_permission_denied(err):
        return (
            "O Google só permite anexar/entregar via API ao projeto que criou a atividade "
            "(ProjectPermissionDenied). Use o modo manual assistido."
        )
    if status == 401:
        return "Credenciais inválidas. Rode `cflow login` novamente."
    if status == 403:
        return (
            "Acesso negado (403). Verifique escopos, se a API está ativada no projeto "
            "ou se o administrador da escola bloqueia apps de terceiros."
        )
    if status == 404:
        return "Recurso não encontrado (404)."
    if status == 429:
        return "Limite de requisições atingido (429). Tente de novo em alguns minutos."
    return f"Erro da API do Google (HTTP {status}): {err}"
