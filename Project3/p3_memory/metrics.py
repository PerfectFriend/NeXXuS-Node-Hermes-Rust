"""Метрики корпуса и поиск (пункты 6 и 7 плана).

Все числа считаются из данных. Ни одна величина отчёта не зашита руками —
иначе отчёт станет правдой только для одного корпуса (такой дефект уже был
в GRAPH_REPORT.md по Project2 и закрыт тестом).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .attribution import attribution
from .canon import corpus
from .loader import DEFAULT_DIR
from .paths import project_root

#: Темы-заглушки: синхронизатор писал их при неудачном разборе источника.
EMPTY_TOPICS = {"unknown", "(unknown)", "", "none", "null", "n/a"}


def is_junk_topic(record: Dict[str, Any]) -> bool:
    """Тема-заглушка или мусорный идентификатор вместо темы."""
    topic = str(record.get("topic") or "").strip().lower()
    if topic in EMPTY_TOPICS:
        return True
    # Мусор скрапера: «X: <id>», «id: ...», «None: None».
    if topic.startswith(("x:", "id:", "none:", "0:")):
        return True
    return not topic


def score_of(record: Dict[str, Any]) -> float:
    value = record.get("relevance_score")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def metrics(memory_dir: Path = DEFAULT_DIR) -> Dict[str, Any]:
    """Метрики канонического корпуса Project3."""
    canon_result = corpus(memory_dir)
    records = canon_result["records"]
    total = len(records)
    junk = [r for r in records if is_junk_topic(r)]
    scores = [score_of(r) for r in records]
    buckets = {"low (<0.6)": 0, "mid (0.6-0.79)": 0, "high (>=0.8)": 0}
    for score in scores:
        if score >= 0.8:
            buckets["high (>=0.8)"] += 1
        elif score >= 0.6:
            buckets["mid (0.6-0.79)"] += 1
        else:
            buckets["low (<0.6)"] += 1
    attribution_result = attribution(canon_result)
    return {
        "files": len(canon_result["files"]),
        "records_total": total,
        "records_input": canon_result["total_input"],
        "duplicates_removed": canon_result["duplicates_removed"],
        "junk_topics": len(junk),
        "junk_ratio": round(len(junk) / total, 6) if total else 0.0,
        "score_mean": round(sum(scores) / total, 4) if total else 0.0,
        "score_max": round(max(scores), 4) if total else 0.0,
        "score_min": round(min(scores), 4) if total else 0.0,
        "score_buckets": buckets,
        "attribution_own": attribution_result["own"],
        "attribution_shared": attribution_result["shared"],
        "attribution_unattributed": attribution_result["unattributed"],
        "by_source_type": attribution_result["by_source_type"],
        "by_category": _counter(records, "category"),
        "duplicates_by_file": canon_result["duplicates_by_file"],
    }


def _counter(records: List[Dict[str, Any]], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        value = str(record.get(field) or "(пусто)")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


#: Веса ранжирования: попадание в текст темы весит больше, чем в сводку.
WEIGHTS = {"topic": 3.0, "tags": 2.0, "summary": 1.0, "category": 0.5, "url": 0.5}


def search(query: str, memory_dir: Path = DEFAULT_DIR,
           category: Optional[str] = None,
           source_type: Optional[str] = None,
           min_score: Optional[float] = None,
           limit: int = 20) -> List[Dict[str, Any]]:
    """Поиск по каноническому корпусу с ранжированием и фильтрами.

    Пустой запрос возвращает записи, прошедшие фильтры, отсортированные
    по релевантности, — это делает поведение предсказуемым и для вызова
    из CLI без поисковой строки.
    """
    canon_result = corpus(memory_dir)
    results: List[Dict[str, Any]] = []
    needle = query.strip().lower()
    for record in canon_result["records"]:
        if category and str(record.get("category") or "").lower() != category.lower():
            continue
        if source_type and str(record.get("source_type") or "").lower() != source_type.lower():
            continue
        score = score_of(record)
        if min_score is not None and score < min_score:
            continue
        rank = score
        if needle:
            haystack = {
                "topic": str(record.get("topic") or ""),
                "tags": " ".join(str(t) for t in (record.get("tags") or [])),
                "summary": str(record.get("summary") or ""),
                "category": str(record.get("category") or ""),
                "url": str(record.get("source_url") or ""),
            }
            hits = sum(
                weight for field, weight in WEIGHTS.items()
                if needle in haystack[field].lower()
            )
            if hits <= 0:
                continue
            rank = round(hits + score, 4)
        results.append({
            "rank": round(rank, 4),
            "relevance": score,
            "topic": record.get("topic"),
            "category": record.get("category"),
            "source_type": record.get("source_type"),
            "occurrences": record.get("_occurrences", 1),
            "sources": list(record.get("_sources") or []),
        })
    results.sort(key=lambda item: (-item["rank"], str(item["topic"])))
    return results[: max(0, limit)]


def report_path() -> Path:
    """Путь отчёта о дублировании внутри проекта."""
    return project_root() / "DUPLICITY_REPORT.md"