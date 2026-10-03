"""Project3 — пакет памяти: загрузка, канонизация, аудит адресации.

Project1 закрыл загрузку/валидацию/дедупликацию инсайтов, Project2 — граф знаний
над корпусом. Этот пакет отвечает на третий вопрос, который корпус Project3
поставил сразу: **проект существует как отдельная сущность или является копией
соседей?** Ответ эмпирический — функциями этого пакета, а не догадкой.

Установленный факт (проверяется `identity.py`, не декларируется):
тело инсайтов Project3 побайтово совпадает с Project1/2/4, потому что
`scripts/professor_sync.py:113` подставляет `applicable_projects=[1,2,3,4]`
при отсутствии поля, и фильтр `project in applicable_projects` становится
тождественно истинным. Правка этого hot-файла — не скоум этого пакета.

Пакет ничего не пишет на диск без явного `--fix`.
"""

__version__ = "1.0.0"

MEMORY_GLOB = "professor_insights_cycle_*.json"
PROJECT_ROOT = "Project3"
SIBLING_PROJECTS = ("Project1", "Project2", "Project4")
MARKERS = ("# HOT", "# COLD")

#: Дефолт адресации в professor_sync.py — источник кросс-проектного дубля.
SYNC_DEFAULT_PROJECTS = (1, 2, 3, 4)

#: Источники, которые в реальности адресованы конкретному проекту, а не всем сразу.
PROJECT_SOURCE_TYPES = {
    "graph": ("graph", "knowledge-graph"),
    "memory": ("memory", "insight", "chronicle"),
    "ui": ("ui", "frontend", "design", "slop"),
    "security": ("security", "harness", "agent"),
}

__all__ = [
    "__version__",
    "MEMORY_GLOB",
    "PROJECT_ROOT",
    "SIBLING_PROJECTS",
    "MARKERS",
    "SYNC_DEFAULT_PROJECTS",
    "PROJECT_SOURCE_TYPES",
]