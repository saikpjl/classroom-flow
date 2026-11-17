"""Consultas à API do Google Classroom (cursos, atividades, submissões)."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

DONE_STATES = {"TURNED_IN", "RETURNED"}


@dataclass(frozen=True)
class Assignment:
    course_id: str
    course_name: str
    id: str
    title: str
    work_type: str          # ASSIGNMENT, SHORT_ANSWER_QUESTION, ...
    link: str               # URL da atividade no Classroom
    due: datetime | None    # já convertido para o fuso local
    api_submittable: bool   # criada pelo MESMO projeto do Google Cloud?


def normalize(text: str) -> str:
    """Minúsculas e sem acentos, para busca tolerante."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def parse_due(cw: dict[str, Any]) -> datetime | None:
    """dueDate/dueTime vêm em UTC. Sem horário definido, assume 23:59 local."""
    d = cw.get("dueDate")
    if not d:
        return None
    if "dueTime" in cw:
        t = cw["dueTime"]
        utc = datetime(d["year"], d["month"], d["day"], t.get("hours", 0), t.get("minutes", 0),
                       tzinfo=timezone.utc)
        return utc.astimezone()
    return datetime(d["year"], d["month"], d["day"], 23, 59).astimezone()


def _paginate(method: Callable, key: str, **params: Any) -> Iterator[dict]:
    token = None
    while True:
        resp = method(pageToken=token, **params).execute()
        yield from resp.get(key, [])
        token = resp.get("nextPageToken")
        if not token:
            return


def list_active_courses(service) -> list[dict]:
    return list(_paginate(service.courses().list, "courses",
                          studentId="me", courseStates=["ACTIVE"]))


def list_assignments(service, course: dict) -> Iterator[Assignment]:
    method = service.courses().courseWork().list
    for cw in _paginate(method, "courseWork", courseId=course["id"],
                        courseWorkStates=["PUBLISHED"]):
        yield Assignment(
            course_id=course["id"],
            course_name=course.get("name", "?"),
            id=cw["id"],
            title=cw.get("title", "(sem título)"),
            work_type=cw.get("workType", "ASSIGNMENT"),
            link=cw.get("alternateLink", ""),
            due=parse_due(cw),
            api_submittable=bool(cw.get("associatedWithDeveloper", False)),
        )


def find_assignments(service, term: str, course_filter: str | None = None) -> list[Assignment]:
    """Busca atividades cujo título contém `term` nas turmas ativas."""
    needle = normalize(term)
    now = datetime.now().astimezone()
    matches: list[Assignment] = []
    for course in list_active_courses(service):
        if course_filter and normalize(course_filter) not in normalize(course.get("name", "")):
            continue
        matches += [a for a in list_assignments(service, course) if needle in normalize(a.title)]
    # Mais próximas de hoje primeiro; sem prazo por último.
    matches.sort(key=lambda a: (a.due is None, abs((a.due - now).total_seconds()) if a.due else 0))
    return matches


def get_my_submission(service, assignment: Assignment) -> dict | None:
    resp = (service.courses().courseWork().studentSubmissions()
            .list(courseId=assignment.course_id, courseWorkId=assignment.id, userId="me")
            .execute())
    subs = resp.get("studentSubmissions", [])
    return subs[0] if subs else None
