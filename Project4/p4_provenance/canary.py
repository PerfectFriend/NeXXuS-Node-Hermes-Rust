"""Канарейка регрессии (пункт 10 плана).

Модуль перепроверяет два свойства, которые однажды были сломаны и должны
ломаться заметно, если сломаются снова:

* дефолтная адресация `applicable_projects=[1,2,3,4]` (дефект фильтра);
* побайтовая идентичность корпуса Project4 соседним проектам.

Вердикт `DRIFT` на штатном дереве — это не авария, а подтверждение, что дефект
жив. На разделённых корпусах ожидается `OK`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional

from . import SIBLING_PROJECTS
from .attribution import default_addressing_audit
from .loader import iter_records, validate_corpus
from .fingerprint import identity_report

OK = "OK"
DRIFT = "DRIFT"

#: Доля дефолтной адресации, выше которой адресация считается сломанной.
DEFAULT_SHARE_THRESHOLD = 0.5


def canary(
    directory: os.PathLike | str,
    repo: os.PathLike | str,
    names: Iterable[str] = SIBLING_PROJECTS,
    default_share_threshold: float = DEFAULT_SHARE_THRESHOLD,
) -> Dict[str, Any]:
    """Прогнать канарейку и вернуть числа, а не только вердикт."""
    records = iter_records(directory)
    addressing = default_addressing_audit(records)
    identity = identity_report(directory, repo, names=names)
    validation = validate_corpus(directory)

    problems: list = []
    if validation["problem_count"]:
        problems.append(
            f"корпус невалиден: {validation['problem_count']} претензий"
        )
    if not records:
        problems.append("корпус пуст — нечего караулить")
    if addressing["default_share"] > default_share_threshold:
        problems.append(
            f"адресация сломана: {addressing['default_addressed']} из "
            f"{addressing['records']} записей с дефолтом "
            f"{addressing['expected_default']}"
        )
    identical = identity["identical_to"]
    if identical:
        problems.append(
            "тело инсайтов совпадает с " + ", ".join(identical)
        )

    return {
        "status": DRIFT if problems else OK,
        "records": addressing["records"],
        "cycles": len(identity["own_fingerprints"]),
        "valid": validation["valid"],
        "validation_problems": validation["problem_count"],
        "default_addressed": addressing["default_addressed"],
        "default_share": addressing["default_share"],
        "identical_to": identical,
        "identical_with_all": identity["identical_with_all"],
        "problems": problems,
        "checks": {
            "корпус валиден": validation["valid"],
            "адресация не дефолтная": addressing["default_share"] <= default_share_threshold,
            "тело уникально для Project4": not identical,
        },
    }


def line(report: Dict[str, Any]) -> str:
    """Одна строка для журнала и для CLI."""
    head = f"{report['status']}: записей {report['records']}, циклов {report['cycles']}, " \
           f"дефолтная адресация {report['default_addressed']}/{report['records']}"
    if report["problems"]:
        return head + "; " + "; ".join(report["problems"])
    return head


def exit_code(report: Dict[str, Any]) -> int:
    """0 при OK, 1 при DRIFT — для использования в CI."""
    return 0 if report["status"] == OK else 1


def separated_canary(root: os.PathLike | str) -> Optional[Dict[str, Any]]:  # pragma: no cover
    """Прогон на синтетически разделённых корпусах (используется в тестах)."""
    return canary(root, root, names=["Project1"])