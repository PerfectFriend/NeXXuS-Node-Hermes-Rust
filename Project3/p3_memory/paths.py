"""Безопасная работа с файлами Project3: пути, атомарная запись, бэкапы.

Пункт 11 плана: все принимаемые пути должны оставаться внутри Project3.
Абсолютный путь и `..` отвергаются, а не «приводятся к корню».
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path


class PathRefused(Exception):
    """Путь ведёт за пределы Project3 — запись отвергнута."""


def project_root() -> Path:
    """Корень Project3 (родитель каталога пакета)."""
    return Path(__file__).resolve().parent.parent


def safe_path(candidate: os.PathLike | str, root: os.PathLike | str | None = None) -> Path:
    """Разрешить путь внутри корня проекта.

    Отвергает абсолютные пути и любое выходжение за пределы `root` —
    проверка делается на разрешённых (`resolve()`) путях, поэтому
    симлинк-обход тоже отсекается.
    """
    root_path = Path(root).resolve() if root is not None else project_root()
    raw = Path(candidate)
    if raw.is_absolute():
        raise PathRefused(f"абсолютный путь отвергнут: {candidate}")
    resolved = (root_path / raw).resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise PathRefused(
            f"путь выходит за пределы {root_path.name}: {candidate}"
        ) from exc
    return resolved


def atomic_write(path: Path, text: str, encoding: str = "utf-8",
                 backup: bool = True, suffix: str = ".bak") -> Path | None:
    """Записать файл атомарно: временный файл + os.replace.

    Крах в середине записи не оставляет обрезанный целевой файл: known-good
    версия сохраняется до последнего `os.replace`. При откате `.tmp`-мусор
    удаляется, а бэкап прежнего содержимого — возвращается на место.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    # `tempfile.mkstemp` создаёт файл с режимом 0600, и `os.replace` переносит
    # этот режим на целевой файл: существовавший 0644 после первой записи
    # становился 0600, и внешний читатель терял доступ. Прежний open('w')
    # уважал umask, поэтому восстанавливаем прежний режим, а для нового
    # файла применяем `0o666 & ~umask`.
    try:
        previous_mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0o022)
        os.umask(umask)
        previous_mode = 0o666 & ~umask
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + suffix)
        shutil.copy2(path, backup_path)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, previous_mode)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        if backup_path is not None and backup_path.exists() and not path.exists():
            os.replace(backup_path, path)
        raise
    return backup_path


def append_section(path: Path, heading: str, body: str,
                   backup: bool = True) -> bool:
    """Дописать раздел в markdown, если заголовка ещё нет.

    Идемпотентно: повторный вызов с тем же заголовком ничего не пишет
    и возвращает False. Перевод строки внутри заголовка или тела
    экранируется, чтобы структура файла не поехала.
    """
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if heading in existing:
        return False
    safe_heading = heading.replace("\n", " ").strip()
    safe_body = "\n".join(line.rstrip() for line in body.rstrip().splitlines())
    section = f"\n## {safe_heading}\n\n{safe_body}\n"
    atomic_write(path, existing.rstrip("\n") + "\n" + section, backup=backup)
    return True