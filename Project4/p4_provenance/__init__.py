"""Project4 — пакет форензики памяти: происхождение и вина данных.

Project1 закрыл загрузку/валидацию/дедупликацию инсайтов, Project2 — граф знаний,
Project3 — кросс-проектную идентичность. Этот пакет отвечает на четвёртый вопрос,
который корпус Project4 поставил сразу: **кто в действительности прислал эти
записи и можно ли доказать дефект живым прогоном, а не цитатой строки?**

Два утверждения, которые этот пакет проверяет, а не декларирует:

1. Тело инсайтов Project4 побайтово совпадает с Project1/2/3
   (проверяет `fingerprint.py`).
2. Причина — дефект адресации в горячем коде `scripts/professor_sync.py:113`:
   при отсутствии поля подставляется `applicable_projects=[1,2,3,4]`, из-за чего
   фильтр `project in applicable_projects` становится тождественно истинным.
   Проверяет `repro.py`, который импортирует НАСТОЯЩИЙ горячий модуль и прогоняет
   его на синтетическом наборе. Правка горячего файла — не скоум этого пакета.

Пакет ничего не пишет на диск без явного `--fix`.
"""

__version__ = "1.0.0"

MEMORY_GLOB = "professor_insights_cycle_*.json"
PROJECT_ROOT = "Project4"
PROJECT_NUMBER = 4
SIBLING_PROJECTS = ("Project1", "Project2", "Project3")
MARKERS = ("# HOT", "# COLD")

#: Дефолт адресации в professor_sync.py — источник кросс-проектного дубля.
SYNC_DEFAULT_PROJECTS = (1, 2, 3, 4)

#: Путь к горячему коду, который порождает память. Только чтение.
SYNC_MODULE_REL = ("scripts", "professor_sync.py")

#: Проект-владелец → ключевые слова в source_type/тегах/тексте записи.
#: Проекты-приёмники выросли из разных кусков протокола, и по этому признаку
#: видно, в чьей работе запись появилась первой.
PROJECT_SOURCE_TYPES = {
    1: ("memory", "dedup", "loader", "valida"),
    2: ("graph", "knowledge-graph", "node", "edge"),
    3: ("identity", "fingerprint", "drift", "compare"),
    4: ("provenance", "forensic", "chain-of-custody", "canary"),
}

__all__ = [
    "__version__",
    "MEMORY_GLOB",
    "PROJECT_ROOT",
    "PROJECT_NUMBER",
    "SIBLING_PROJECTS",
    "MARKERS",
    "SYNC_DEFAULT_PROJECTS",
    "SYNC_MODULE_REL",
    "PROJECT_SOURCE_TYPES",
]