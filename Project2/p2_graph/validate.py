"""Валидация, дедупликация и фильтрация инсайтов Project2.

Мусор, измеренный на штатных данных (2 файла, 190 инсайтов):
- 6 записей с topic "Unknown" и/или пустым summary;
- 4 дубликата (topic, source_url);
- 6 записей без source_url.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from . import VALID_PROJECTS

REQUIRED_FIELDS = (
    "topic",
    "category",
    "summary",
    "source_url",
    "source_type",
    "relevance_score",
    "applicable_projects",
    "tags",
    "timestamp",
)

LIST_FIELDS = ("applicable_projects", "tags")
STR_FIELDS = ("topic", "category", "summary", "source_url", "source_type", "timestamp")

UNKNOWN_TOPIC = "Unknown"


def validate_insight(item: Any, where: str = "insight") -> List[str]:
    """Вернуть список проблем одной записи (пусто — запись валидна)."""
    problems: List[str] = []
    if not isinstance(item, dict):
        return [f"{where}: ожидался объект, получен {type(item).__name__}"]

    for field in REQUIRED_FIELDS:
        if field not in item:
            problems.append(f"{where}: нет поля {field!r}")

    for field in STR_FIELDS:
        if field in item and not isinstance(item[field], str):
            problems.append(f"{where}.{field}: ожидалась строка, получено {type(item[field]).__name__}")

    for field in LIST_FIELDS:
        if field in item and not isinstance(item[field], list):
            problems.append(f"{where}.{field}: ожидался список, получено {type(item[field]).__name__}")

    score = item.get("relevance_score")
    if "relevance_score" in item:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            problems.append(f"{where}.relevance_score: ожидалось число, получено {type(score).__name__}")
        elif not 0.0 <= float(score) <= 1.0:
            problems.append(f"{where}.relevance_score: {score} вне диапазона 0..1")

    topic = item.get("topic")
    if isinstance(topic, str) and topic.strip() == "":
        problems.append(f"{where}.topic: пустая строка")

    projects = item.get("applicable_projects")
    if isinstance(projects, list):
        for p in projects:
            if p not in VALID_PROJECTS:
                problems.append(f"{where}.applicable_projects: {p!r} вне {list(VALID_PROJECTS)}")

    return problems


def validate_file(data: Dict[str, Any]) -> List[str]:
    """Проверить memory-файл целиком, включая согласованность total_insights."""
    problems: List[str] = []
    name = data.get("_path", "?")
    insights = data.get("insights")
    if not isinstance(insights, list):
        return [f"{name}: поле insights не список"]

    declared = data.get("total_insights")
    if isinstance(declared, int) and declared != len(insights):
        problems.append(
            f"{name}: total_insights={declared}, а записей {len(insights)}"
        )
    for idx, item in enumerate(insights):
        problems.extend(validate_insight(item, where=f"{name}[{idx}]"))
    return problems


def is_junk(item: Any) -> Tuple[bool, str]:
    """Мусор ли запись. Возвращает (мусор?, причина).

    Принимает `Any` намеренно: мусор — это в том числе не-объекты, а проверить
    это можно только приняв их.
    """
    if not isinstance(item, dict):
        return True, "не объект"
    if item.get("topic") == UNKNOWN_TOPIC:
        return True, f"topic == {UNKNOWN_TOPIC!r}"
    topic = item.get("topic")
    if isinstance(topic, str) and not topic.strip():
        return True, "пустой topic"
    summary = item.get("summary")
    if isinstance(summary, str) and not summary.strip():
        return True, "пустой summary"
    return False, ""


def find_duplicates(insights: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str], List[int]]:
    """Индексы дублей по ключу (topic, source_url)."""
    seen: Dict[Tuple[str, str], List[int]] = {}
    for idx, item in enumerate(insights):
        if not isinstance(item, dict):
            continue
        key = (str(item.get("topic", "")), str(item.get("source_url", "")))
        seen.setdefault(key, []).append(idx)
    return {k: v for k, v in seen.items() if len(v) > 1}


def clean_insights(insights: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Вернуть (очищенный список, статистика). Ничего не мутирует на входе."""
    kept: List[Dict[str, Any]] = []
    stats = {
        "total": len(insights),
        "junk": 0,
        "duplicates": 0,
        "junk_reasons": {},
    }
    seen_keys = set()
    for idx, item in enumerate(insights):
        junk, reason = is_junk(item)
        if junk:
            stats["junk"] += 1
            stats["junk_reasons"][reason] = stats["junk_reasons"].get(reason, 0) + 1
            continue
        key = (str(item.get("topic", "")), str(item.get("source_url", "")))
        if key in seen_keys:
            stats["duplicates"] += 1
            continue
        seen_keys.add(key)
        kept.append(item)
    stats["kept"] = len(kept)
    return kept, stats
