"""Атомарная дописка записей в CHRONICLE.md.

Зачем это кодом, а не ручной правкой: журнал проекта правится агентами
Протокола Живого Кода каждый слот. Ручная вставка ломает хвост файла
(срезанный заголовок или потерянный блок), а `git add` в монорепо LivingCode
коммитит весь репозиторий — нужен предсказуемый, проверяемый аппенд.

Правила:
- запись добавляется В КОНЕЦ файла, ничего не переписывая;
- перед записью файла ставится метка времени из аргумента (без wall-clock
  внутри функции — детерминизм нужен тестам);
- запись атомарна: write-to-tmp + os.replace, рядом живёт .bak;
- повторная запись с тем же заголовком НЕ дублируется (защита от
  повторного прогона в одном слоте).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

CHRONICLE_NAME = "CHRONICLE.md"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def render_entry(title: str, body: str, stamp: str) -> str:
    """Собрать текст одной записи журнала (без завершающих разделителей)."""
    lines: List[str] = [f"### {stamp} — {title.strip()}"]
    for raw in body.strip().splitlines():
        lines.append(raw.rstrip())
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def has_entry(text: str, title: str) -> bool:
    """Есть ли в тексте запись с таким заголовком."""
    needle = f" — {title.strip()}"
    return any(line.startswith("### ") and line.endswith(needle) for line in text.splitlines())


def append_entry(chronicle: Path, title: str, body: str, stamp: str) -> Path:
    """Дописать запись в CHRONICLE.md. Возвращает путь к файлу.

    Если запись с таким заголовком уже есть — файл не меняется (no-op).
    """
    path = Path(chronicle)
    if not title.strip():
        raise ValueError("заголовок записи пуст")
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise OSError(f"{path}: не читается ({exc})") from exc

    if existing and has_entry(existing, title):
        return path

    entry = render_entry(title, body, stamp)
    prefix = ""
    if existing and not existing.endswith("\n"):
        prefix = "\n"          # не съедаем последнюю строку файла
    elif existing and not existing.endswith("\n\n"):
        prefix = "\n"
    payload = existing + prefix + entry

    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def now_stamp(moment: datetime) -> str:
    """Метка времени для заголовка записи."""
    return moment.strftime(TIMESTAMP_FORMAT)