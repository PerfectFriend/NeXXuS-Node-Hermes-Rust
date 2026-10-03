"""Загрузка memory-файлов Project2.

Дефект, который закрывает модуль: маркер-скрипт LivingCode дописывал строку
`# HOT` в начало файлов без учёта расширения. Для `.json` это ломало файл
целиком (json.JSONDecodeError), и синхронизация Профессора падала.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import MARKERS, MEMORY_GLOB

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "memory"


class MemoryError_(Exception):
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


def load(path: os.PathLike | str) -> Dict[str, Any]:
    """Прочитать один memory-файл. Терпим к маркеру в первой строке."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MemoryError_(f"{path}: не читается ({exc})") from exc
    clean, removed = strip_markers(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        hint = f" (сняты маркеры: {', '.join(removed)})" if removed else ""
        raise MemoryError_(f"{path}: невалидный JSON{hint}: {exc}") from exc
    if not isinstance(data, dict):
        raise MemoryError_(f"{path}: ожидался объект, получен {type(data).__name__}")
    if not isinstance(data.get("insights"), list):
        raise MemoryError_(f"{path}: поле insights отсутствует или не список")
    data.setdefault("total_insights", len(data["insights"]))
    data["_markers_removed"] = removed
    data["_path"] = str(path)
    return data


def memory_files(directory: os.PathLike | str | None = None) -> List[Path]:
    """Отсортированный список memory-файлов каталога."""
    root = Path(directory) if directory else DEFAULT_DIR
    if not root.is_dir():
        raise MemoryError_(f"{root}: каталог памяти не найден")
    return sorted(root.glob(MEMORY_GLOB))


def load_all(directory: os.PathLike | str | None = None) -> List[Dict[str, Any]]:
    """Прочитать все memory-файлы каталога по возрастанию номера цикла."""
    out: List[Dict[str, Any]] = []
    for path in memory_files(directory):
        data = load(path)
        data["_cycle"] = _cycle_of(path)
        out.append(data)
    return out


def _cycle_of(path: Path) -> int:
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    return int(digits) if digits else -1


def iter_insights(files: List[Dict[str, Any]]):
    """Пройти по инсайтам, добавляя служебные поля file/cycle/index."""
    for data in files:
        for idx, item in enumerate(data["insights"]):
            if not isinstance(item, dict):
                continue
            enriched = dict(item)
            enriched["_file"] = Path(data["_path"]).name
            enriched["_cycle"] = data.get("_cycle", -1)
            enriched["_index"] = idx
            yield enriched


def atomic_write(
    path: os.PathLike | str, data: Dict[str, Any], backup: bool = True
) -> "Path | None":
    """Записать JSON атомарно: write-to-tmp + os.replace, с бэкапом исходника.

    Гарантии: при сбое сериализации known-good файл не тронут, временный
    файл удаляется. Возвращает путь к бэкапу (или None, если бэкап не делался).
    """
    path = Path(path)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    backup_path: Path | None = None
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return backup_path
