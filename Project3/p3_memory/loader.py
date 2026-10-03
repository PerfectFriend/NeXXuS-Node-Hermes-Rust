"""Загрузка и валидация memory-файлов Project3 (пункт 1 плана).

Дефект, который закрывает загрузчик: скрипт маркировки LivingCode дописывал
строку `# HOT` в начало файлов без учёта расширения. Для `.json` это ломало
файл целиком (`json.JSONDecodeError`), и чтение памяти падало.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import MARKERS, MEMORY_GLOB, SYNC_DEFAULT_PROJECTS

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "memory"

#: Обязательные поля записи инсайта.
REQUIRED_FIELDS = ("topic", "category", "summary")

#: Поля, для которых тип проверяется жёстко.
FIELD_TYPES = {
    "topic": str,
    "category": str,
    "summary": str,
    "source_url": str,
    "source_type": str,
    "relevance_score": (int, float),
    "applicable_projects": list,
    "tags": list,
    "timestamp": str,
}


class MemoryInvalid(Exception):
    """Память не читается или не имеет ожидаемой структуры."""


def strip_markers(text: str) -> Tuple[str, List[str]]:
    """Убрать строки-маркеры LivingCode из начала текста.

    Возвращает (очищенный текст, список снятых маркеров).
    """
    removed: List[str] = []
    lines = text.splitlines(keepends=True)
    while lines:
        head = lines[0].strip()
        if head in MARKERS:
            removed.append(head)
            lines.pop(0)
            continue
        break
    return "".join(lines), removed


def read_text(path: os.PathLike | str) -> Tuple[Dict[str, Any], List[str]]:
    """Прочитать один memory-файл, сняв маркер. Возвращает (данные, маркеры)."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MemoryInvalid(f"{path.name}: не читается ({exc})") from exc
    clean, removed = strip_markers(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        hint = f" (сняты маркеры: {', '.join(removed)})" if removed else ""
        raise MemoryInvalid(
            f"{path.name}: невалидный JSON{hint}: {exc.msg} (строка {exc.lineno})"
        ) from exc
    if not isinstance(data, dict):
        raise MemoryInvalid(
            f"{path.name}: ожидался объект, получен {type(data).__name__}"
        )
    return data, removed


def load(path: os.PathLike | str) -> Dict[str, Any]:
    """Прочитать один memory-файл и проверить каркас схемы."""
    path = Path(path)
    data, removed = read_text(path)
    if not isinstance(data.get("insights"), list):
        raise MemoryInvalid(f"{path.name}: поле insights отсутствует или не список")
    if "total_insights" in data and data["total_insights"] != len(data["insights"]):
        raise MemoryInvalid(
            f"{path.name}: total_insights={data['total_insights']} "
            f"не совпадает с числом записей {len(data['insights'])}"
        )
    data.setdefault("total_insights", len(data["insights"]))
    data["_markers_removed"] = removed
    data["_source_file"] = path.name
    return data


def discover(memory_dir: os.PathLike | str = DEFAULT_DIR) -> List[Path]:
    """Все memory-файлы проекта, отсортированные по имени цикла."""
    return sorted(Path(memory_dir).glob(MEMORY_GLOB))


def validate_insight(record: Any, where: str) -> List[str]:
    """Проверить одну запись. Возвращает список претензий (пустой — годна)."""
    problems: List[str] = []
    if not isinstance(record, dict):
        return [f"{where}: запись не объект ({type(record).__name__})"]
    for field in REQUIRED_FIELDS:
        if field not in record:
            problems.append(f"{where}: нет поля {field!r}")
    for field, expected in FIELD_TYPES.items():
        if field in record and not isinstance(record[field], expected):
            problems.append(
                f"{where}: поле {field!r} имеет тип "
                f"{type(record[field]).__name__}, ожидался "
                f"{'/'.join(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__}"
            )
    score = record.get("relevance_score")
    # `bool` — подкласс `int` в Python, поэтому без этой проверки `True`
    # проходил как валидная релевантность.
    if isinstance(score, bool):
        problems.append(f"{where}: поле 'relevance_score' имеет тип bool, ожидался int/float")
    elif isinstance(score, (int, float)):
        if not 0.0 <= float(score) <= 1.0:
            problems.append(f"{where}: relevance_score={score} вне [0, 1]")
    projects = record.get("applicable_projects")
    if isinstance(projects, list):
        for item in projects:
            if not isinstance(item, int) or isinstance(item, bool):
                problems.append(f"{where}: applicable_projects содержит не целое {item!r}")
    return problems


def validate_file(path: os.PathLike | str) -> List[str]:
    """Полная проверка одного файла. Бросает MemoryInvalid, если файл нечитаем."""
    path = Path(path)
    data, _ = read_text(path)
    problems: List[str] = []
    if "cycle" in data and not isinstance(data["cycle"], int):
        problems.append(f"{path.name}: cycle не целое")
    if "project" in data and data["project"] != 3:
        problems.append(
            f"{path.name}: файл помечен project={data['project']}, а лежит в Project3"
        )
    for index, record in enumerate(data.get("insights") or []):
        problems.extend(validate_insight(record, f"{path.name}[{index}]"))
    if data.get("total_insights") is not None and isinstance(data.get("insights"), list):
        if data["total_insights"] != len(data["insights"]):
            problems.append(
                f"{path.name}: total_insights={data['total_insights']} "
                f"!= {len(data['insights'])}"
            )
    return problems


def validate_corpus(memory_dir: os.PathLike | str = DEFAULT_DIR) -> Dict[str, Any]:
    """Проверить весь корпус проекта. Не бросает исключений — собирает итог."""
    files = discover(memory_dir)
    per_file: Dict[str, List[str]] = {}
    unreadable: List[str] = []
    total_records = 0
    for path in files:
        try:
            problems = validate_file(path)
        except MemoryInvalid as exc:
            unreadable.append(str(exc))
            per_file[path.name] = [str(exc)]
            continue
        per_file[path.name] = problems
        data, _ = read_text(path)
        total_records += len(data.get("insights") or [])
    all_problems = [p for probs in per_file.values() for p in probs]
    return {
        "files": len(files),
        "file_names": [p.name for p in files],
        "records": total_records,
        "problem_count": len(all_problems),
        "problems": all_problems,
        "unreadable": unreadable,
        "per_file": per_file,
        "valid": not all_problems,
    }


def is_default_addressed(record: Dict[str, Any]) -> bool:
    """Запись адресована всем проектам — признак дефолта синхронизатора.

    Именно такие записи делают Project1..4 побайтово одинаковыми.
    """
    projects = record.get("applicable_projects")
    return isinstance(projects, list) and tuple(projects) == SYNC_DEFAULT_PROJECTS