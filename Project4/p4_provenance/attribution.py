"""Атрибуция записей: чья это в действительности память (пункт 4 плана).

Два утверждения, которые модуль проверяет, а не декларирует:

1. `applicable_projects` для форензики бесполезен: у всех записей корпуса оно
   равно дефолту `[1,2,3,4]` (проверяет `default_addressing_audit`), то есть поле
   не несёт информации о происхождении.
2. Тема записи — тоже не признак происхождения. Проверено на живом корпусе:
   184 из 190 записей имеют `source_type=textbook`, и большинство тем —
   «Graph Engineering Fundamentals», «Autonomous Graph Evolution Protocols» и т.п.
   Наивная эвристика по слову «graph» приписала бы весь учебник Project2.
   Происхождение видно не по теме, а по служебным меткам `source_type`/тегам.

Поэтому порядок разбора такой: сначала отсеивается общая учебно-дайджестовая
масса (`textbook-core`), и только среди оставшегося ищутся проектные маркеры.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Tuple

from . import PROJECT_SOURCE_TYPES, SYNC_DEFAULT_PROJECTS
from .loader import is_default_addressed

#: Признаки общей учебно-дайджестовой массы: такие записи по определению
#: одинаковы для всех приёмников и не принадлежат ни одному проекту.
CORE_MARKERS = ("textbook", "learned", "учебник", "textbook.md")

TEXTBOOK_CORE = "textbook-core"
BORROWED_PREFIX = "borrowed-all"


def _has_keyword(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in keywords)


def haystack(record: Dict[str, Any]) -> str:
    """Служебные признаки записи: тип источника, теги, категория, время.

    Тема и текст резюме НЕ входят: тема учебника о графах не делает запись
    достоянием Project2 — это и была ошибка первой версии эвристики.
    """
    parts = [
        str(record.get("source_type", "")),
        str(record.get("category", "")),
        str(record.get("timestamp", "")),
    ]
    parts.extend(str(tag) for tag in (record.get("tags") or []))
    return " ".join(parts)


def owner_guess(record: Dict[str, Any]) -> str:
    """Наиболее вероятный «владелец» записи по её служебным признакам."""
    if _has_keyword(haystack(record), CORE_MARKERS):
        return TEXTBOOK_CORE
    service = haystack(record)
    for project, keywords in PROJECT_SOURCE_TYPES.items():
        if _has_keyword(service, keywords):
            return f"project{project}-ish"
    address_note = "default" if is_default_addressed(record) else "explicit"
    return f"{BORROWED_PREFIX}/{address_note}"


def attribute_corpus(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Разложить корпус по группам происхождения."""
    groups: Dict[str, Dict[str, Any]] = {}
    for record in records:
        owner = owner_guess(record)
        bucket = groups.setdefault(
            owner, {"count": 0, "cycles": set(), "topics": [], "default_addressed": 0}
        )
        bucket["count"] += 1
        if record.get("_cycle") is not None:
            bucket["cycles"].add(record["_cycle"])
        if is_default_addressed(record):
            bucket["default_addressed"] += 1
        topic = str(record.get("topic", ""))
        if topic and len(bucket["topics"]) < 10:
            bucket["topics"].append(topic)

    total = sum(b["count"] for b in groups.values()) or 1
    serialised: Dict[str, Dict[str, Any]] = {}
    for name, bucket in sorted(groups.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        serialised[name] = {
            "count": bucket["count"],
            "share": round(bucket["count"] / total, 6),
            "cycles": sorted(bucket["cycles"]),
            "default_addressed": bucket["default_addressed"],
            "sample_topics": bucket["topics"],
        }
    core = serialised.get(TEXTBOOK_CORE, {}).get("count", 0)
    borrowed = core + sum(
        b["count"] for name, b in serialised.items() if name.startswith(BORROWED_PREFIX)
    )
    own = sum(
        b["count"] for name, b in serialised.items() if name.endswith("-ish")
    )
    if core / total >= 0.5:
        verdict = (
            "у Project4 нет собственного ядра: корпус — общая учебно-дайджестовая "
            "масса, одинаковая для всех приёмников"
        )
    elif own / total >= 0.5:
        verdict = "у корпуса есть собственное ядро"
    else:
        verdict = "корпус смешанный: есть и своё, и заимствованное"
    return {
        "total_records": total,
        "groups": serialised,
        "core_total": core,
        "core_share": round(core / total, 6),
        "borrowed_total": borrowed,
        "borrowed_share": round(borrowed / total, 6),
        "own_total": own,
        "own_share": round(own / total, 6),
        "explicitly_addressed": sum(
            b["count"]
            for b in serialised.values()
            if b["default_addressed"] < b["count"]
        ),
        "verdict": verdict,
    }


def default_addressing_audit(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Доля записей с дефолтной адресацией и распределение по наборам проектов."""
    records = list(records)
    total = len(records) or 1
    default = sum(1 for r in records if is_default_addressed(r))
    shapes: Dict[Tuple[int, ...], int] = {}
    for record in records:
        projects = record.get("applicable_projects")
        if isinstance(projects, list):
            shapes[tuple(projects)] = shapes.get(tuple(projects), 0) + 1
    return {
        "records": len(records),
        "default_addressed": default,
        "default_share": round(default / total, 6),
        "expected_default": list(SYNC_DEFAULT_PROJECTS),
        "filter_can_discriminate": default < len(records),
        "addressing_shapes": {
            "[" + ",".join(map(str, k)) + "]": v for k, v in sorted(shapes.items())
        },
    }


def repetition_report(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Повторы внутри проекта: одна тема в нескольких записях.

    Отдельная мера, потому что 190 записей против 101 уникальной темы — это
    либо осознанное накопление, либо деградация синхронизации; вывод делает
    число, а не догадка.
    """
    records = list(records)
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        by_topic.setdefault(str(record.get("topic", "")), []).append(record)
    repeated = {topic: items for topic, items in by_topic.items() if len(items) > 1}
    duplicated_records = sum(len(items) - 1 for items in repeated.values())
    worst = sorted(repeated.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:10]
    return {
        "records": len(records),
        "unique_topics": len(by_topic),
        "repeated_topics": len(repeated),
        "duplicate_records": duplicated_records,
        "duplicate_share": round(duplicated_records / len(records), 6) if records else 0.0,
        "worst": [{"topic": topic, "count": len(items)} for topic, items in worst],
    }