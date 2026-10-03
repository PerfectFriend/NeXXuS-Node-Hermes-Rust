"""Атрибуция записей и аудит адресации (пункты 4 и 5 плана).

Две связанные задачи:

**Атрибуция.** `applicable_projects` для оценки «чьи это инсайты» использовать
нельзя: на штатном корпусе поле у всех записей равно `[1,2,3,4]`, то есть
несёт нулевую информацию. Поэтому принадлежность проекту оценивается по
содержанию — типу источника и тегам.

**Аудит адресации.** Разбор того, почему все четыре проекта получили
одинаковые данные: доля записей с дефолтной адресацией и проверка самой
гипотезы дефекта фильтра в `professor_sync.sync_to_project`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from . import SYNC_DEFAULT_PROJECTS
from .loader import DEFAULT_DIR, is_default_addressed

PROJECT_NUMBER = 3

#: Типы источников, которые в действительности относятся к этому проекту.
#: У Project3 (память/граф/загрузка) — память, инсайты, chronicle и knowledge.
OWN_SOURCE_HINTS = ("memory", "insight", "chronicle", "knowledge", "memory_sync")

#: Метки, которые продублированы во всех чистых записях и потому
#: информации о принадлежности не дают (замер сделан на штатном корпусе).
UNINFORMATIVE_TAGS = ("learned", "textbook")


def source_of(record: Dict[str, Any]) -> str:
    return str(record.get("source_type") or "").strip().lower()


def tags_of(record: Dict[str, Any]) -> List[str]:
    raw = record.get("tags")
    if not isinstance(raw, list):
        return []
    return [str(tag).strip().lower() for tag in raw if str(tag).strip()]


def informative_tags(record: Dict[str, Any]) -> List[str]:
    """Теги, несущие информацию (без общеразпространённых меток)."""
    return [tag for tag in tags_of(record) if tag not in UNINFORMATIVE_TAGS]


def attributed_to_project(record: Dict[str, Any],
                          project: int = PROJECT_NUMBER) -> Optional[str]:
    """Кому принадлежит запись по содержанию.

    Возвращает `own` (запись действительно про этот проект), `shared`
    (общая для всех) или None — признаков принадлежности нет.
    Поле `applicable_projects` намеренно не используется: см. модульный докстринг.
    """
    hints = OWN_SOURCE_HINTS if project == 3 else ()
    stype = source_of(record)
    tags = set(tags_of(record))
    if hints and stype in hints:
        return "own"
    if hints and tags & set(hints):
        return "own"
    if tags:
        return "shared"
    return None


def attribution(canon_result: Dict[str, Any],
                project: int = PROJECT_NUMBER) -> Dict[str, Any]:
    """Разложить канонический корпус по принадлежности.

    Ключи результата: own, shared, unattributed, by_source_type, total.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {"own": [], "shared": [], "unattributed": []}
    by_source: Dict[str, int] = {}
    for record in canon_result["records"]:
        verdict = attributed_to_project(record, project)
        buckets[verdict or "unattributed"].append(record)
        stype = source_of(record) or "(пусто)"
        by_source[stype] = by_source.get(stype, 0) + 1
    return {
        "own": len(buckets["own"]),
        "shared": len(buckets["shared"]),
        "unattributed": len(buckets["unattributed"]),
        "total": len(canon_result["records"]),
        "by_source_type": dict(sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))),
        "own_keys": [r["_key"] for r in buckets["own"]],
    }


#: Поведение фильтра из professor_sync.py:125, вынесено отдельно, чтобы
#: гипотезу дефекта можно было проверить, не импортируя hot-код.
def sync_filter_passes(project: int, applicable_projects: Any) -> bool:
    """Ровно то условие, которое использует professor_sync.sync_to_project."""
    return isinstance(applicable_projects, list) and project in applicable_projects


def audit_addressing(records: Iterable[Dict[str, Any]],
                     project: int = PROJECT_NUMBER) -> Dict[str, Any]:
    """Разбор адресации: сколько записей ушло во все проекты.

    Поля результата:
      total                    — число записей;
      default_addressed        — сколько с `applicable_projects == [1,2,3,4]`;
      default_ratio            — их доля;
      project_addressed        — сколько адресовано Project3;
      filter_works             — может ли фильтр вообще что-то отсечь
                                 (True, если на корпусе есть хотя бы одна запись,
                                 НЕ адресованная Project3);
      excluded_count           — сколько записей фильтр отсёк бы;
      offenders                — имена файлов-источников дефолтных записей;
      verdict                  — человекочитаемый вывод.
    """
    records = list(records)
    total = len(records)
    default_records = [r for r in records if is_default_addressed(r)]
    non_default = [r for r in records if not is_default_addressed(r)]
    excluded = [r for r in records if not sync_filter_passes(project, r.get("applicable_projects"))]
    filter_works = len(excluded) > 0
    ratio = round(len(default_records) / total, 6) if total else 0.0
    if not total:
        verdict = "корпус пуст — вывода нет"
    elif filter_works:
        verdict = (
            f"адресация различает проекты: фильтр отсёк бы {len(excluded)} из {total}"
        )
    else:
        verdict = (
            f"адресация вырождена: {len(default_records)} из {total} записей "
            f"(доля {ratio:.3f}) помечены всеми проектами сразу, фильтр в "
            f"professor_sync.py:125 не может ничего отсечь — проекты получают "
            f"идентичные данные"
        )
    offenders = sorted({
        name
        for record in default_records
        for name in (record.get("_sources") or [])
    })
    return {
        "total": total,
        "default_addressed": len(default_records),
        "default_ratio": ratio,
        "project_addressed": sum(
            1 for r in records if sync_filter_passes(project, r.get("applicable_projects"))
        ),
        "filter_works": filter_works,
        "excluded_count": len(excluded),
        "distinct_non_default_addressing": len(
            {tuple(r.get("applicable_projects") or []) for r in non_default}
        ),
        "offenders": offenders,
        "verdict": verdict,
    }


def addressing_from_disk(memory_dir: Path = DEFAULT_DIR) -> Dict[str, Any]:
    """Аудит адресации по штатному корпусу проекта (записи со служебными полями)."""
    from .canon import read_all

    records = []
    for data in read_all(memory_dir):
        for record in data.get("insights") or []:
            item = dict(record)
            item["_sources"] = [data.get("_source_file")]
            records.append(item)
    return audit_addressing(records)