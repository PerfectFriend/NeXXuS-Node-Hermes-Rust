"""Метрики корпуса, деградации и поиск с фильтрами (пункты 5 и 6 плана).

Все числа вычисляются из корпуса, ни одна константа не зашита. Для форензики
важнее не «красивая сводка», а способность отличить здоровое накопление от
деградации: 190 записей против 101 уникальной темы — это либо осознанное
накопление, либо повторная доставка одного и того же, и вывод должен делать
счётчик, а не догадка.
"""

from __future__ import annotations

import os
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple


# --------------------------------------------------------------------------
# пункт 5 — метрики
# --------------------------------------------------------------------------


def empty_topics(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Записи с пустой или пробельной темой — первый признак деградации."""
    return [
        {"cycle": r.get("_cycle"), "source_file": r.get("_source_file")}
        for r in records
        if not str(r.get("topic", "")).strip()
    ]


def missing_fields(records: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Сколько записей не содержат каждое из ключевых полей."""
    records = list(records)
    out: Dict[str, int] = {}
    for field in ("topic", "category", "summary", "relevance_score", "source_url"):
        out[field] = sum(1 for r in records if not str(r.get(field, "")).strip())
    return out


def relevance_histogram(records: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Распределение релевантности по шагам в 0.1."""
    histogram: Dict[str, int] = {}
    for record in records:
        score = record.get("relevance_score")
        value = float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else 0.0
        bucket = f"{min(int(value * 10), 9) / 10:.1f}"
        histogram[bucket] = histogram.get(bucket, 0) + 1
    return {key: histogram[key] for key in sorted(histogram)}


def metrics(
    records: Iterable[Dict[str, Any]],
    source_types: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Сводные метрики корпуса."""
    from .attribution import attribute_corpus, default_addressing_audit, repetition_report

    records = list(records)
    total = len(records)
    cycles = sorted({r["_cycle"] for r in records if r.get("_cycle") is not None})
    per_cycle = Counter(r.get("_cycle") for r in records)
    categories = Counter(str(r.get("category", "")) for r in records)
    types = Counter(str(r.get("source_type", "")) for r in records)
    blanks = empty_topics(records)
    attribution_report = attribute_corpus(records)
    repeats = repetition_report(records)

    return {
        "records": total,
        "cycles": cycles,
        "cycle_count": len(cycles),
        "per_cycle": {str(k): v for k, v in sorted(per_cycle.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "categories": dict(categories.most_common()),
        "source_types": dict(types.most_common()) if source_types is None else source_types,
        "unique_topics": repeats["unique_topics"],
        "duplicate_records": repeats["duplicate_records"],
        "duplicate_share": repeats["duplicate_share"],
        "empty_topics": len(blanks),
        "empty_topic_examples": blanks[:5],
        "missing_fields": missing_fields(records),
        "relevance": relevance_histogram(records),
        "default_addressing_share": default_addressing_audit(records)["default_share"],
        "core_share": attribution_report["core_share"],
        "own_share": attribution_report["own_share"],
        "verdict": attribution_report["verdict"],
    }


# --------------------------------------------------------------------------
# пункт 6 — поиск и фильтры
# --------------------------------------------------------------------------


def _haystack(record: Dict[str, Any]) -> str:
    parts = [
        str(record.get("topic", "")),
        str(record.get("summary", "")),
        str(record.get("category", "")),
        str(record.get("source_type", "")),
        str(record.get("source_url", "")),
    ]
    parts.extend(str(tag) for tag in (record.get("tags") or []))
    return " ".join(parts).lower()


def relevance_of(record: Dict[str, Any]) -> float:
    score = record.get("relevance_score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        return float(score)
    return 0.0


def filter_records(
    records: Iterable[Dict[str, Any]],
    topic: Optional[str] = None,
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    cycle: Optional[int] = None,
    tags: Optional[Iterable[str]] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Отбор по полям. Пустой фильтр означает «все записи», а не «ничего»."""
    result = list(records)
    if topic:
        needle = topic.lower()
        result = [r for r in result if needle in str(r.get("topic", "")).lower()]
    if category:
        needle = category.lower()
        result = [r for r in result if needle in str(r.get("category", "")).lower()]
    if source_type:
        needle = source_type.lower()
        result = [r for r in result if needle in str(r.get("source_type", "")).lower()]
    if cycle is not None:
        result = [r for r in result if r.get("_cycle") == cycle]
    if tags:
        wanted = {str(t).lower() for t in tags}
        result = [r for r in result if wanted & {str(t).lower() for t in (r.get("tags") or [])}]
    if min_score is not None:
        result = [r for r in result if relevance_of(r) >= min_score]
    if max_score is not None:
        result = [r for r in result if relevance_of(r) <= max_score]
    return result


def score_record(record: Dict[str, Any], needle: str) -> float:
    """Вес совпадения: точное начало темы > тема > всё остальное."""
    if not needle:
        return 0.0
    needle = needle.lower()
    topic = str(record.get("topic", "")).lower()
    if topic == needle:
        return 1.0
    if topic.startswith(needle):
        return 0.8
    if needle in topic:
        return 0.6
    if needle in _haystack(record):
        return 0.3
    return 0.0


def search(
    records: Iterable[Dict[str, Any]],
    query: str,
    limit: int = 20,
    **filters: Any,
) -> List[Dict[str, Any]]:
    """Поиск с ранжированием и фильтрами.

    Записи с нулевым весом отбрасываются: иначе «найденное» — это весь корпус
    с припиской, что в отчёте выглядело бы как результат.
    """
    if not query:
        return []
    hits = []
    for record in filter_records(records, **filters):
        weight = score_record(record, query)
        if weight > 0.0:
            hits.append((weight, relevance_of(record), record))
    # Сначала вес совпадения, потом релевантность как вторичный признак.
    hits.sort(key=lambda item: (-item[0], -item[1], str(item[2].get("topic", ""))))
    return [
        {"weight": round(w, 3), "record": r} for w, _, r in hits[: max(0, limit)]
    ]


def search_summary(
    records: Iterable[Dict[str, Any]], query: str, **filters: Any
) -> Dict[str, Any]:
    """Поиск вместе с числами — для CLI и отчёта."""
    hits = search(records, query, limit=1000, **filters)
    return {
        "query": query,
        "filters": {k: v for k, v in filters.items() if v not in (None, [], "")},
        "hits": len(hits),
        "top": hits[:10],
    }


def unique_filter_values(records: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Список значений для подсказок CLI — из данных, а не из догадок."""
    records = list(records)
    categories = Counter(str(r.get("category", "")) for r in records)
    types = Counter(str(r.get("source_type", "")) for r in records)
    tags: Counter = Counter()
    for record in records:
        for tag in record.get("tags") or []:
            tags[str(tag)] += 1
    return {
        "categories": [name for name, _ in categories.most_common()],
        "source_types": [name for name, _ in types.most_common()],
        "tags": [name for name, _ in tags.most_common()],
    }