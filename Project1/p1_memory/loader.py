"""Загрузка и запись memory-файлов Project1.

Дефект, который закрывает этот модуль: маркер-скрипт LivingCode дописывал
строку `# HOT` в начало файлов без учёта расширения. Для `.json` это ломало
файл целиком (json.JSONDecodeError), и синхронизация Профессора падала.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

MARKERS = ("# HOT", "# COLD")


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


def load(path: Path) -> Dict[str, Any]:
    """Прочитать memory-файл. Терпим к маркеру в первой строке."""
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


def save_atomic(path: Path, data: Dict[str, Any], backup: bool = True) -> Path:
    """Атомарно перезаписать memory-файл: write-to-tmp + os.replace.

    Прерванная запись не может обнулить файл: known-good остаётся на диске
    до момента os.replace. При backup=True исходник сохраняется в .bak.
    """
    path = Path(path)
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def iter_memory_files(project_root: Path) -> List[Path]:
    """Все memory-файлы проекта, отсортированные по имени."""
    from . import MEMORY_GLOB

    memory_dir = Path(project_root) / "memory"
    if not memory_dir.is_dir():
        return []
    return sorted(memory_dir.glob(MEMORY_GLOB))