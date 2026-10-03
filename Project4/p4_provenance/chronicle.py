"""Безопасная запись в CHRONICLE.md (пункт 12 плана).

Требования, из-за которых модуль существует отдельно, а не как три строки в
конце скрипта:

* запись атомарна (через временный файл и `os.replace`) — прерванный слот не
  оставляет после себя обрезанный CHRONICLE;
* перед записью делается `.bak`, поэтому прошлый текст всегда восстановим;
* заголовок слота не дублируется: повторный запуск того же слота дописывает
  в существующий блок, а не создаёт второй;
* путь обязан лежать внутри Project4.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .paths import PROJECT_DIR, inside_root

CHRONICLE_REL = "CHRONICLE.md"


class ChronicleError(Exception):
    """Запись в хронику не удалась."""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def slot_heading(title: str, when: Optional[str] = None) -> str:
    """Заголовок блока слота."""
    return f"## Слот {when or _now()} — {title}"


def _heading_pattern(heading: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)


def has_slot(text: str, heading: str) -> bool:
    """Есть ли уже такой блок в хронике."""
    return bool(_heading_pattern(heading).search(text))


def append_slot(
    body: str,
    title: str,
    when: Optional[str] = None,
    chronicle: os.PathLike | str = CHRONICLE_REL,
    root: Path = PROJECT_DIR,
) -> Path:
    """Дописать блок слота в CHRONICLE.md атомарно, без дублей заголовка."""
    target = inside_root(chronicle, root)
    heading = slot_heading(title, when)
    block = f"{heading}\n\n{body.rstrip()}\n"

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if has_slot(existing, heading):
        raise ChronicleError(f"блок слота уже есть в хронике: {heading}")

    # Между прежним текстом и новым блоком должен быть пустой отступ: иначе
    # последняя строка предыдущего блока склеится с заголовком.
    if not existing:
        prefix = ""
    elif existing.endswith("\n\n"):
        prefix = ""
    elif existing.endswith("\n"):
        prefix = "\n"
    else:
        prefix = "\n\n"
    payload = existing + prefix + block

    backup = target.with_suffix(target.suffix + ".bak")
    if target.exists():
        shutil.copy2(target, backup)

    handle, temp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=".chronicle-", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        os.replace(temp_name, target)
    except OSError as exc:  # noqa: BLE001 — причина показывается как есть
        raise ChronicleError(f"не удалось записать хронику: {exc}") from exc
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return target


def append_slot_safe(
    body: str,
    title: str,
    when: Optional[str] = None,
    chronicle: os.PathLike | str = CHRONICLE_REL,
    root: Path = PROJECT_DIR,
) -> Optional[Path]:
    """То же, но без исключений: дубль заголовка — это уже записанный слот."""
    try:
        return append_slot(body, title, when, chronicle, root)
    except ChronicleError:
        return None