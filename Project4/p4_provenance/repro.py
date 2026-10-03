"""Живое воспроизведение дефекта адресации (пункт 3 плана).

Заявление, которое модуль проверяет: дефект виден не в чтении строки
`applicable_projects=data.get("applicable_projects", [1,2,3,4])`, а в прогоне
НАСТОЯЩЕГО горячего кода. Поэтому здесь импортируется живой
`scripts/professor_sync.py` (только чтение, файл не правится) и проверяются три
вещи живьём:

1. `_create_insight` без поля `applicable_projects` выдаёт дефолтную адресацию —
   то есть не адресовать конкретный проект невозможно, а «забыть поле» означает
   «отправить всем четырём».
2. `sync_to_project` пропускает в файл проекта инсайты, которые этому проекту
   не принадлежат: фильтр `project in applicable_projects` становится тождественно
   истинным при дефолтной адресации.
3. На синтетическом наборе с РЕАЛЬНО различающейся адресацией фильтр работает —
   то есть ломается именно дефолт, а не механизм фильтрации.

Прогон идёт на временном корне: горячий `sync_to_project` пишет файлы и делает
git-коммит, поэтому `root` экземпляра подменяется на каталог вне репозитория.
Живой файл при этом не изменяется ни на байт.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

from .paths import sync_module


class HotModuleMissing(Exception):
    """Горячий модуль синхронизатора не найден или не импортируется."""


def load_hot_module(repo: os.PathLike | str) -> ModuleType:
    """Импортировать живой `scripts/professor_sync.py` по пути, без правок файла."""
    path = sync_module(repo)
    if not path.exists():
        raise HotModuleMissing(f"нет горячего модуля: {path}")
    spec = importlib.util.spec_from_file_location("p4_hot_professor_sync", path)
    if spec is None or spec.loader is None:
        raise HotModuleMissing(f"не удалось описать модуль: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — причину показываем как есть
        raise HotModuleMissing(f"модуль не импортируется: {exc}") from exc
    return module


def hot_source_line(repo: os.PathLike | str, needle: str = "applicable_projects") -> str:
    """Строка горячего файла, задающая дефолт адресации (для отчёта)."""
    path = sync_module(repo)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line and "data.get" in line:
            return f"{path.name}:{number}: {line.strip()}"
    return f"{path.name}: строка с дефолтом не найдена"


def _sync(root: Path, module: ModuleType, cycle: int):
    sync = module.ProfessorSync(cycle)
    sync.root = root
    sync.vault_root = root / "vault"
    return sync


def repro_default_addressing(repo: os.PathLike | str) -> Dict[str, Any]:
    """Прогон: запись без адресации попадает во все проекты подряд."""
    module = load_hot_module(repo)
    with tempfile.TemporaryDirectory(prefix="p4-repro-") as tmp:
        root = Path(tmp)
        sync = _sync(root, module, 777)

        payload: Dict[str, Any] = {
            "topic": "Пробная тема без адресации",
            "category": "AI Engineering",
            "summary": "синтетическая запись для воспроизведения",
            "source_type": "web",
            "relevance_score": 0.7,
        }
        insight = sync._create_insight(payload)

        per_project: Dict[str, int] = {}
        for project in (1, 2, 3, 4):
            result = sync.sync_to_project(project, [insight])
            per_project[f"Project{project}"] = int(result.get("synced", 0))

        return {
            "default_addressing": list(insight.applicable_projects),
            "addressing_is_default": tuple(insight.applicable_projects) == (1, 2, 3, 4),
            "synced_per_project": per_project,
            "leaked_everywhere": set(per_project.values()) == {1},
            "filter_broken": all(v == 1 for v in per_project.values()),
            "hot_source_line": hot_source_line(repo),
        }


def repro_filter_works_with_real_addressing(repo: os.PathLike | str) -> Dict[str, Any]:
    """Прогон-контроль: при реальной адресации фильтр отбирает верно.

    Если этот тест зелёный, то виноват не механизм фильтрации, а дефолт в
    `_create_insight` — это и есть содержание дефекта.
    """
    module = load_hot_module(repo)
    with tempfile.TemporaryDirectory(prefix="p4-repro-ok-") as tmp:
        root = Path(tmp)
        sync = _sync(root, module, 778)

        mine = sync._create_insight(
            {
                "topic": "Только для Project4",
                "category": "Textbook",
                "summary": "адресована одному проекту",
                "applicable_projects": [4],
            }
        )
        foreign = sync._create_insight(
            {
                "topic": "Только для Project2",
                "category": "Textbook",
                "summary": "адресована другому проекту",
                "applicable_projects": [2],
            }
        )

        result4 = sync.sync_to_project(4, [mine, foreign])
        result2 = sync.sync_to_project(2, [mine, foreign])
        memory4 = sync.root / "Project4" / "memory"
        stored = sorted(p.name for p in memory4.glob("*.json")) if memory4.exists() else []
        return {
            "project4_synced": int(result4.get("synced", 0)),
            "project2_synced": int(result2.get("synced", 0)),
            "filter_works": int(result4.get("synced", 0)) == 1
            and int(result2.get("synced", 0)) == 1,
            "project4_files": stored,
        }


def repro_report(repo: os.PathLike | str) -> Dict[str, Any]:
    """Оба прогона вместе — то, что печатает CLI и попадает в отчёт."""
    broken = repro_default_addressing(repo)
    control = repro_filter_works_with_real_addressing(repo)
    return {
        "default_addressing_case": broken,
        "real_addressing_control": control,
        "diagnosis": (
            "дефолт applicable_projects=[1,2,3,4] делает фильтр "
            "project in applicable_projects тождественно истинным; "
            "при реальной адресации фильтр работает верно"
            if broken["filter_broken"] and control["filter_works"]
            else "наблюдение не подтвердило гипотезу — см. числа выше"
        ),
        "defect_confirmed": bool(broken["filter_broken"] and control["filter_works"]),
    }


def dry_defect_summary(repo: os.PathLike | str) -> Optional[str]:  # pragma: no cover
    try:
        return repro_report(repo)["diagnosis"]
    except HotModuleMissing as exc:
        return f"горячий модуль недоступен: {exc}"