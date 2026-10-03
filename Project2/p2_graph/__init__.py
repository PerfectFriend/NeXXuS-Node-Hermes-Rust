"""Project2 — граф знаний над корпусом памяти Профессора.

Project1 закрыл загрузку/валидацию/дедупликацию инсайтов. Этот пакет идёт дальше
и превращает корпус Project2 (184 инсайта, все — темы графовой инженерии) в
граф: узлы, рёбра четырёх типов, метрики, связные компоненты, центральность,
поиск и CLI.

Дефект данных, который закрывает загрузчик: скрипт маркировки LivingCode
дописывал строку `# HOT` в начало файлов без учёта расширения, и `.json`
переставал быть валидным JSON целиком.

Пакет ничего не пишет на диск без явного `--fix`.
"""

__version__ = "1.0.0"

MEMORY_GLOB = "professor_insights_cycle_*.json"
VALID_PROJECTS = (1, 2, 3, 4)
MARKERS = ("# HOT", "# COLD")

EDGE_TYPES = (
    "same_source",
    "same_topic",
    "shares_tag",
    "same_category",
    "token_overlap",
)

__all__ = [
    "__version__",
    "MEMORY_GLOB",
    "VALID_PROJECTS",
    "MARKERS",
    "EDGE_TYPES",
]
