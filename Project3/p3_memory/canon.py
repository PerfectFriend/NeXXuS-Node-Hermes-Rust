"""Канонизация корпуса Project3 (пункт 3 плана).

Собирает все memory-файлы проекта в единый список записей, дедуплицируя по
нормализованному ключу «тема + категория + URL», и помня, из каких файлов
и в каком порядке запись появилась.

Замер, который обязан сойтись: внутри проекта повторов **0** (дедуп снимает
только межцикловое совпадение), а 84 пересечения существуют лишь на
объединённом корпусе — то есть между соседними проектами, не внутри.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import PROJECT_ROOT
from .loader import DEFAULT_DIR, discover, load

_WS = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    """Нормализовать строку для ключа: регистр, пробелы, крайние символы."""
    if value is None:
        return ""
    return _WS.sub(" ", str(value).strip().lower())


def record_key(record: Dict[str, Any]) -> str:
    """Ключ дедупликации: тема + категория + URL.

    URL нормализуется до схемы+хоста+пути без query и хвоста, чтобы
    `https://x.com/i/status/1?utm=…` и `https://x.com/i/status/1` сошлись.
    """
    topic = normalize_text(record.get("topic"))
    category = normalize_text(record.get("category"))
    url = normalize_text(record.get("source_url"))
    url = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not url and topic:
        # Запись без источника различается только текстом сводки.
        return f"{topic}|{category}|{normalize_text(record.get('summary'))[:120]}"
    return f"{topic}|{category}|{url}"


def read_all(memory_dir: Path = DEFAULT_DIR) -> List[Dict[str, Any]]:
    """Прочитать все файлы проекта, каждый — с проверенной схемой."""
    files: List[Dict[str, Any]] = []
    for path in discover(memory_dir):
        data = load(path)
        files.append(data)
    return files


def canon(files: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Свести файлы в канонический корпус с дедупликацией.

    Возвращает словарь:
      records   — уникальные записи, каждая с `_sources` (файлы) и
                  `_first_file` (где встретилась впервые);
      keys      — множество ключей;
      duplicates_by_file — сколько записей в файле оказались повторами
                  уже собранных (внутри проекта это ожидаемо между циклами);
      total_input — сколько записей было на входе.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    total_input = 0
    duplicates_by_file: Dict[str, int] = {}

    for data in files:
        name = data.get("_source_file", "?")
        duplicates_here = 0
        for record in data.get("insights") or []:
            total_input += 1
            key = record_key(record)
            if key in seen:
                duplicates_here += 1
                entry = seen[key]
                if name not in entry["_sources"]:
                    entry["_sources"].append(name)
                entry["_occurrences"] += 1
                continue
            entry = dict(record)
            entry["_key"] = key
            entry["_sources"] = [name]
            entry["_first_file"] = name
            entry["_occurrences"] = 1
            seen[key] = entry
            order.append(key)
        duplicates_by_file[name] = duplicates_here

    records = [seen[key] for key in order]
    return {
        "records": records,
        "keys": set(order),
        "total_input": total_input,
        "unique": len(records),
        "duplicates_removed": total_input - len(records),
        "duplicates_by_file": duplicates_by_file,
    }


def corpus(memory_dir: Path = DEFAULT_DIR) -> Dict[str, Any]:
    """Штатная точка входа: прочитать проект и вернуть канонический корпус."""
    files = read_all(memory_dir)
    result = canon(files)
    result["memory_dir"] = str(memory_dir)
    result["files"] = [d.get("_source_file") for d in files]
    return result


def unique_count_vs_sibling(canon_result: Dict[str, Any], sibling_keys: Iterable[str]) -> int:
    """Сколько записей Project3 не совпадает ни с одним ключом соседа."""
    foreign = set(sibling_keys)
    return sum(1 for record in canon_result["records"] if record["_key"] not in foreign)


def dump_json(canon_result: Dict[str, Any]) -> str:
    """Сериализовать канонический корпус в JSON (без служебных полей)."""
    clean = []
    for record in canon_result["records"]:
        item = {
            key: value
            for key, value in record.items()
            if not key.startswith("_")
        }
        item["sources"] = list(record.get("_sources", []))
        item["occurrences"] = record.get("_occurrences", 1)
        clean.append(item)
    return json.dumps(clean, ensure_ascii=False, indent=2)


def save_canon(canon_result: Dict[str, Any], path: Path,
               fix: bool = False) -> Optional[Path]:
    """Записать канонический корпус на диск. Без `fix=True` только читает."""
    if not fix:
        return None
    from .paths import atomic_write
    text = dump_json(canon_result)
    return atomic_write(Path(path), text)