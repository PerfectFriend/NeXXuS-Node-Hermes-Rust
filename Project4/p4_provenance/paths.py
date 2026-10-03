"""Разрешение путей строго внутри Project4 (пункт 11 плана).

Все файловые операции пакета проходят через `inside_root()`. Абсолютные пути и
`..` отвергаются: запись памяти приёмника не должна дотягиваться до соседних
проектов, даже если её вызвали с путём вида `../Project3/...`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from . import PROJECT_ROOT

#: Корень проекта: родитель каталога пакета.
PROJECT_DIR = Path(__file__).resolve().parent.parent
#: Репозиторий LivingCode: родитель каталога Project4.
REPO_DIR = PROJECT_DIR.parent

PathLike = Union[str, os.PathLike]


class PathOutsideProject(Exception):
    """Путь ведёт за пределы Project4."""


def inside_root(path: PathLike, root: PathLike = PROJECT_DIR) -> Path:
    """Вернуть `path`, разрешённый относительно корня проекта.

    Абсолютный путь отвергается: у пакета нет ни одной легитимной причины
    писать по абсолютному пути, а проверка на каждом вызове дешевле, чем разбор
    случая в аудите.
    """
    root = Path(root).resolve()
    raw = Path(path)
    if raw.is_absolute():
        raise PathOutsideProject(f"абсолютный путь отвергнут: {raw}")
    if any(part == ".." for part in raw.parts):
        raise PathOutsideProject(f"'..' в пути отвергнут: {raw}")
    resolved = (root / raw).resolve()
    if resolved != root and root not in resolved.parents:
        raise PathOutsideProject(f"путь выходит за корень {root.name}: {raw}")
    return resolved


def memory_dir(root: PathLike = PROJECT_DIR) -> Path:
    """Каталог memory-файлов Project4."""
    return inside_root("memory", root)


def sibling_memory_dir(name: str, repo: PathLike = REPO_DIR) -> Path:
    """Каталог memory соседнего проекта — только для чтения (сверка отпечатков)."""
    if not name.startswith("Project") or name == PROJECT_ROOT:
        raise PathOutsideProject(f"не имя проекта-соседа: {name}")
    candidate = (Path(repo).resolve() / name / "memory").resolve()
    if candidate.parent.parent != Path(repo).resolve():
        raise PathOutsideProject(f"выход за пределы репозитория: {name}")
    return candidate


def sync_module(repo: PathLike = REPO_DIR) -> Path:
    """Путь к горячему `scripts/professor_sync.py` — только чтение."""
    from . import SYNC_MODULE_REL

    candidate = Path(repo).resolve().joinpath(*SYNC_MODULE_REL)
    if candidate.parent.parent != Path(repo).resolve():
        raise PathOutsideProject("путь к горячему модулю вне репозитория")
    return candidate