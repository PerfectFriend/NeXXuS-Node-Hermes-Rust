"""Канонизация корпуса: одна запись — один источник (пункт 7 плана).

Задача, которую ставит перед канонизацией форензика: из 190 записей корпуса
уникальных тем 101. Прежде чем считать это деградацией, нужно убрать технический
повтор — те же знания, доставленные дважды. Канонический ключ нормализует тему
(регистр, пробелы, типографские тире) и URL, поэтому «Graph Engineering
Fundamentals» и «graph engineering fundamentals» — одна и та же запись, а не две.
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Пунктуация, которую схлопывает нормализация. Тире всех сортов в тексте тем
#: встречаются вперемешку, и без этого одна тема распадалась бы на четыре.
_DASHES = dict.fromkeys(
    map(ord, "‐‑‒–—―−－"), "-"
)
_PUNCT = re.compile(r"[^\w\s-]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Привести тему к канону: NFKC, тире, пунктуация, пробелы, регистр."""
    value = unicodedata.normalize("NFKC", str(text))
    value = value.translate(_DASHES).lower()
    value = _PUNCT.sub(" ", value)
    value = _SPACES.sub(" ", value).strip()
    return value


def normalise_url(url: str) -> str:
    """URL в канон: без схемы, `www.`, завершающего слэша и пробелов."""
    value = unicodedata.normalize("NFKC", str(url)).strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    if value.startswith("www."):
        value = value[4:]
    return value.rstrip("/")


def canon_key(record: Dict[str, Any]) -> Tuple[str, str, str]:
    """Ключ канонической записи: тема + категория + URL."""
    return (
        normalise_text(record.get("topic", "")),
        normalise_text(record.get("category", "")),
        normalise_url(record.get("source_url", "")),
    )


def _best_of(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Канонический представитель группы: наивысшая релевантность, затем поздний цикл.

    Ранний цикл проигрывает сознательно: при двух доставках одной мысли полезнее
    та, что позже, — в ней исправления предыдущей.
    """
    def rank(record: Dict[str, Any]) -> Tuple[float, int]:
        score = record.get("relevance_score")
        value = float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else 0.0
        cycle = record.get("_cycle")
        return (value, cycle if isinstance(cycle, int) else -1)

    return max(records, key=rank)


def canonicalise(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Свести корпус к уникальным записям со счётчиком источников.

    Возвращает и список канонических записей, и числа деградации: сколько
    записей было, сколько осталось и откуда каждая пришла.
    """
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(canon_key(record), []).append(record)

    canonical: List[Dict[str, Any]] = []
    # Записи с пустой темой нельзя склеивать: у них ключ совпадает только если
    # совпали ещё и категория с URL, а если совпали — это уже настоящая копия.
    # Поэтому пустая тема отсекается по первой компоненте ключа.
    for key, members in groups.items():
        if not key[0]:
            continue
        best = _best_of(members)
        origin = sorted(
            {
                f"cycle-{m['_cycle']}:{m.get('_source_file', '?')}"
                for m in members
                if m.get("_cycle") is not None
            }
        )
        entry = dict(best)
        entry["_canon_key"] = "|".join(key)
        entry["_sources"] = origin
        entry["_occurrences"] = len(members)
        canonical.append(entry)

    # Пустые темы разбираются отдельно и в основной проход не попадают.
    blank_groups = [m for key, members in groups.items() if not key[0] for m in members]
    for index, member in enumerate(blank_groups):
        entry = dict(member)
        entry["_canon_key"] = f"<пустая тема #{index}>"
        entry["_sources"] = []
        entry["_occurrences"] = 1
        canonical.append(entry)

    total = sum(len(members) for members in groups.values())
    canonical.sort(key=lambda r: (-r.get("_occurrences", 1), str(r.get("topic", ""))))

    duplicates = [
        {
            "topic": key[0] or "<пустая тема>",
            "occurrences": len(members),
            "sources": sorted(
                {
                    f"cycle-{m['_cycle']}:{m.get('_source_file', '?')}"
                    for m in members
                    if m.get("_cycle") is not None
                }
            ),
        }
        for key, members in sorted(
            groups.items(), key=lambda kv: (-len(kv[1]), kv[0])
        )
        if len(members) > 1 and key[0]
    ]

    return {
        "records_in": total,
        "canonical_out": len(canonical),
        "duplicate_records": total - len(canonical),
        "dedup_ratio": round((total - len(canonical)) / total, 6) if total else 0.0,
        "duplicate_groups": len(duplicates),
        "duplicates": duplicates,
        "records": canonical,
    }


def only_mine(
    canonical: Dict[str, Any], other: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    """Какие канонические записи Project4 не встречаются у соседа."""
    from .fingerprint import record_key

    others = {record_key(r) for r in other}
    unique = [r for r in canonical["records"] if record_key(r) not in others]
    return {
        "own_records": len(unique),
        "share": round(len(unique) / canonical["canonical_out"], 6)
        if canonical["canonical_out"]
        else 0.0,
        "topics": [str(r.get("topic", "")) for r in unique[:20]],
    }


def write_canonical_json(canonical: Dict[str, Any], path: os.PathLike | str) -> None:
    """Записать канонический корпус. Путь обязан лежать внутри Project4.

    Путь разрешается относительно корня проекта, поэтому абсолютные пути и
    `..` отвергаются — иначе пакет смог бы писать в соседний проект, а это
    ровно то, ради чего пункт 11 плана существует. Вызывающий, которому нужен
    произвольный каталог (тесты, отчёт вне дерева), передаёт относительный путь
    от корня Project4.
    """
    import json

    from .paths import inside_root

    target = inside_root(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "records_in": canonical["records_in"],
        "canonical_out": canonical["canonical_out"],
        "duplicate_records": canonical["duplicate_records"],
        "duplicate_groups": canonical["duplicate_groups"],
        "records": [
            {
                "topic": r.get("topic"),
                "category": r.get("category"),
                "source_type": r.get("source_type"),
                "relevance_score": r.get("relevance_score"),
                "source_url": r.get("source_url"),
                "tags": r.get("tags"),
                "occurrences": r.get("_occurrences"),
                "sources": r.get("_sources"),
            }
            for r in canonical["records"]
        ],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )