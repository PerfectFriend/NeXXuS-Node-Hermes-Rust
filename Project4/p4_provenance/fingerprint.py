"""Отпечатки корпуса и кросс-проектная идентичность (пункт 2 плана).

Утверждение, которое модуль проверяет, а не декларирует: тело инсайтов Project4
побайтово совпадает с соседними проектами. Проверка идёт по каноническому хэшу
тела (без полей `project`/`synced_at`) и по попарному пересечению ключей записей.

Почему хэш, а не `diff`: тело — это список словарей, и побайтовое сравнение
файлов ломается от перестановки ключей в JSON, хотя данные те же. Канонизация
приводит структуру к строке, где порядок ключей и отступы не имеют значения.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import SIBLING_PROJECTS
from .loader import iter_records, load
from .paths import sibling_memory_dir

#: Поля, которые НЕ участвуют в отпечатке тела: они описывают доставку, а не запись.
EXCLUDED_FIELDS = ("project", "synced_at")

#: Служебные поля, добавленные загрузчиком, — тоже вне отпечатка.
SERVICE_PREFIX = "_"


def canonical_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Запись без полей доставки и служебных полей."""
    return {
        key: value
        for key, value in record.items()
        if key not in EXCLUDED_FIELDS and not key.startswith(SERVICE_PREFIX)
    }


def canonical_body(data: Dict[str, Any]) -> str:
    """Каноническая строка тела инсайтов одного файла."""
    records = [canonical_record(r) for r in data.get("insights") or []]
    return json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def body_digest(data: Dict[str, Any]) -> str:
    """SHA-256 канонического тела (совпадает у тел с одинаковыми записями)."""
    return hashlib.sha256(canonical_body(data).encode("utf-8")).hexdigest()


def file_digest(path: os.PathLike | str) -> str:
    """SHA-256 сырого байтового содержимого файла — для отладки совпадений."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def corpus_fingerprints(directory: os.PathLike | str) -> Dict[int, Dict[str, Any]]:
    """Отпечатки всех циклов корпуса: цикл → {digest, records, file}.

    Цикл берётся из данных файла, а не из имени: имя — это соглашение, цикл —
    это факт в данных.
    """
    from .loader import discover

    out: Dict[Any, Dict[str, Any]] = {}
    for path in discover(directory):
        data = load(path)
        cycle = data.get("cycle")
        out[cycle] = {
            "cycle": cycle,
            "digest": body_digest(data),
            "file_digest": file_digest(path),
            "records": len(data.get("insights") or []),
            "file": path.name,
            "project": data.get("project"),
        }
    return out


def record_key(record: Dict[str, Any]) -> Tuple[str, str, str]:
    """Ключ записи для попарного сравнения корпусов разных проектов."""
    canonical = canonical_record(record)
    return (
        str(canonical.get("topic", "")),
        str(canonical.get("category", "")),
        str(canonical.get("source_url", "")),
    )


def compare_bodies(
    mine: Dict[Any, str], other: Dict[Any, str]
) -> Dict[str, Any]:
    """Сравнить отпечатки циклов двух проектов.

    `identical` требует совпадения не только по общим циклам, но и по множеству
    циклов целиком: если у соседа есть лишний цикл, корпуса не идентичны, даже
    когда все общие циклы совпали до байта. Иначе расхождение спряталось бы за
    равенством пересечения.
    """
    shared = sorted(set(mine) & set(other))
    equal = [c for c in shared if mine[c] == other[c]]
    different = [c for c in shared if mine[c] != other[c]]
    only_mine = sorted(set(mine) - set(other))
    only_other = sorted(set(other) - set(mine))
    return {
        "shared_cycles": shared,
        "identical_cycles": equal,
        "divergent_cycles": different,
        "only_mine": only_mine,
        "only_other": only_other,
        "identical": bool(shared) and len(equal) == len(shared) and not only_mine and not only_other,
    }


def key_overlap(mine: Iterable[Dict[str, Any]], other: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Пересечение множеств ключей записей — независимая мера совпадения."""
    a = {record_key(r) for r in mine}
    b = {record_key(r) for r in other}
    common = a & b
    return {
        "mine_unique": len(a),
        "other_unique": len(b),
        "shared": len(common),
        "jaccard": round(len(common) / len(a | b), 6) if (a or b) else 0.0,
        "only_mine": sorted(a - b)[:20],
    }


def neighbour_names() -> Tuple[str, ...]:
    return SIBLING_PROJECTS


def identity_report(
    directory: os.PathLike | str,
    repo: os.PathLike | str,
    names: Iterable[str] = SIBLING_PROJECTS,
) -> Dict[str, Any]:
    """Полная сверка Project4 с каждым соседним проектом.

    Две независимые меры: хэш тела (жёсткая) и пересечение ключей (мягкая, ловит
    случай «то же самое, но с другой припиской»).
    """
    mine = {
        cycle: info["digest"] for cycle, info in corpus_fingerprints(directory).items()
    }
    mine_records = iter_records(directory)
    neighbours: Dict[str, Any] = {}
    for name in names:
        other_dir = sibling_memory_dir(name, repo)
        if not other_dir.exists():
            neighbours[name] = {"present": False}
            continue
        other = {
            cycle: info["digest"]
            for cycle, info in corpus_fingerprints(other_dir).items()
        }
        other_records = iter_records(other_dir)
        neighbours[name] = {
            "present": True,
            "body": compare_bodies(mine, other),
            "keys": key_overlap(mine_records, other_records),
        }
    identical = [
        name
        for name, info in neighbours.items()
        if info.get("present") and info["body"]["identical"]
    ]
    return {
        "project": "Project4",
        "own_fingerprints": corpus_fingerprints(directory),
        "neighbours": neighbours,
        "identical_to": identical,
        "identical_with_all": len(identical) == len(neighbours) and bool(identical),
    }


def content_digest_of_records(records: Iterable[Dict[str, Any]]) -> Optional[str]:
    """Хэш набора записей, приведённых к канону — для синтетических корпусов."""
    canonical = [canonical_record(r) for r in records]
    if not canonical:
        return None
    blob = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()