"""Валидация, дедупликация и фильтрация инсайтов Project1.

Мусор, измеренный на штатных данных (2 файла, 190 инсайтов):
- 6 записей с topic "Unknown" и/или пустым summary;
- 4 дубликата (topic, source_url);
- 6 записей без source_url.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote

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
            problems.append(f"{where}: отсутствует поле '{field}'")

    for field in STR_FIELDS:
        value = item.get(field)
        if field in item and not isinstance(value, str):
            problems.append(f"{where}: поле '{field}' должно быть строкой, получено {type(value).__name__}")

    for field in LIST_FIELDS:
        value = item.get(field)
        if field in item and not isinstance(value, list):
            problems.append(f"{where}: поле '{field}' должно быть списком, получено {type(value).__name__}")

    if isinstance(item.get("topic"), str) and not item["topic"].strip():
        problems.append(f"{where}: пустой topic")

    score = item.get("relevance_score")
    if "relevance_score" in item:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            problems.append(f"{where}: relevance_score должен быть числом, получено {type(score).__name__}")
        elif not 0.0 <= float(score) <= 1.0:
            problems.append(f"{where}: relevance_score вне диапазона 0..1 ({score})")

    projects = item.get("applicable_projects")
    if isinstance(projects, list):
        unknown = [p for p in projects if p not in VALID_PROJECTS]
        if unknown:
            problems.append(f"{where}: неизвестные applicable_projects {unknown}")

    tags = item.get("tags")
    if isinstance(tags, list):
        bad = [t for t in tags if not isinstance(t, str)]
        if bad:
            problems.append(f"{where}: нестроковые теги {bad}")

    return problems


def validate_document(data: Dict[str, Any]) -> List[str]:
    """Проверить весь memory-документ, включая его заголовок."""
    path = data.get("_path", "<память>")
    problems: List[str] = []

    for field, expected in (("cycle", int), ("project", int), ("synced_at", str)):
        value = data.get(field)
        if field not in data:
            problems.append(f"{path}: отсутствует поле '{field}'")
        elif isinstance(value, bool) or not isinstance(value, expected):
            problems.append(f"{path}: поле '{field}' должно быть {expected.__name__}")

    declared = data.get("total_insights")
    insights = data.get("insights") or []
    if isinstance(declared, int) and declared != len(insights):
        problems.append(f"{path}: total_insights={declared}, фактически {len(insights)}")

    for index, item in enumerate(insights):
        problems.extend(validate_insight(item, where=f"{path} insights[{index}]"))

    return problems


def is_junk(item: Any) -> bool:
    """Мусорная запись: неизвестная или пустая тема, либо пустая выжимка."""
    if not isinstance(item, dict):
        return True
    raw_topic = item.get("topic")
    raw_summary = item.get("summary")
    topic = raw_topic.strip() if isinstance(raw_topic, str) else ""
    summary = raw_summary.strip() if isinstance(raw_summary, str) else ""
    return (not topic) or topic == UNKNOWN_TOPIC or (not summary)


def normalize_source_url(url: Any) -> str:
    """Канонический вид source_url для сравнения.

    Одна и та же заметка может прийти как `Dataview%20Mastery.md` и как
    `Dataview Mastery.md`, а также со схемой в разном регистре или с
    завершающим `/`. Процентное кодирование и регистр схемы/хоста не
    несут смысла, поэтому сравнивать их по коду бессмысленно — дубль
    проходит как новая мысль.
    """
    text = unquote(str(url).strip())
    text = re.sub(r"\s+", " ", text)
    scheme, sep, rest = text.partition("://")
    if sep:
        host, slash, tail = rest.partition("/")
        text = scheme.lower() + sep + host.lower() + slash + tail
    return text.rstrip("/") if text.count("/") > 2 else text


def dedupe_key(item: Dict[str, Any]) -> Tuple[str, str]:
    topic = item.get("topic") if isinstance(item.get("topic"), str) else ""
    url = item.get("source_url") if isinstance(item.get("source_url"), str) else ""
    return topic.strip().casefold(), normalize_source_url(url)


def clean_insights(insights: List[Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Отбросить мусор и дубли. Возвращает (чистые записи, счётчики)."""
    kept: List[Dict[str, Any]] = []
    seen = set()
    junk_count = 0
    dup_count = 0

    for item in insights:
        if is_junk(item):
            junk_count += 1
            continue
        key = dedupe_key(item)
        if key in seen:
            dup_count += 1
            continue
        seen.add(key)
        kept.append(item)

    stats = {
        "input": len(insights),
        "junk": junk_count,
        "duplicates": dup_count,
        "kept": len(kept),
    }
    return kept, stats


def summarize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Числовая сводка по одному memory-файлу (сырые данные, без чистки)."""
    insights = data.get("insights") or []
    kept, stats = clean_insights(insights)
    topics = {dedupe_key(i)[0] for i in kept}
    return {
        "path": data.get("_path", ""),
        "cycle": data.get("cycle"),
        "synced_at": data.get("synced_at", ""),
        "markers_removed": data.get("_markers_removed", []),
        "raw": stats,
        "unique_topics": len(topics),
        "problems": validate_document(data),
    }