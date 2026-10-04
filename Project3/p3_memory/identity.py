"""Детектор кросс-проектной идентичности (пункт 2 плана).

Отвечает на вопрос, который корпус Project3 поставил сразу: существует ли
проект как отдельная сущность памяти или он копия соседей?

Метод: тело `insights` (без полей `project`/`synced_at`) нормализуется
в канонический JSON и сравнивается по SHA-256. Дополнительно считается
пересечение множеств ключей — на случай, когда тела разошлись, но записи
те же.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import SIBLING_PROJECTS
from .canon import canon, read_all
from .loader import DEFAULT_DIR, load
from .paths import project_root

#: Поля, которые различаются по построению и не характеризуют содержимое.
IGNORED_FIELDS = ("project", "synced_at", "_markers_removed", "_source_file")

#: Служебная надстройка, которую соседний проект может дописать в запись.
#:
#: `superseded_by` появляется у кодера Project2 (пункт 19 его плана:
#: `freshness --fix` размечает подменённое происхождение), `origin_issue` —
#: его диагностическая пометка о происхождении записи. Это пометки о
#: происхождении, а не само содержание: тема, категория, URL, релевантность
#: и текст от них не зависят.
#:
#: Установлено живой пробой 2026-10-04: надстройка покрывает 94 записи
#: Project2 из 190 (`superseded_by` × 87, `origin_issue` × 7), при этом после
#: её снятия тела Project3 и Project2 совпадают в точности — хэш содержания
#: один и тот же. То есть именно надстройка была причиной расхождения
#: побайтовых хэшей. Список ограничен этими двумя полями: любое другое
#: различие (в том числе правка темы, URL или текста) остаётся содержательным
#: и обязано ломать `identical`.
SERVICE_FIELDS = ("superseded_by", "origin_issue")


def livingcode_root() -> Path:
    """Корень LivingCode (родитель каталога Project3)."""
    return project_root().parent


def body_canonical(data: Dict[str, Any], drop_service: bool = True) -> str:
    """Каноническая строка тела insights без служебных полей.

    `drop_service=True` (по умолчанию) выбрасывает из каждой записи поля
    `SERVICE_FIELDS` — служебную надстройку соседа. `drop_service=False`
    даёт строку «как есть в файле» — по ней считается побайтовое расхождение.
    """
    payload = {
        key: value for key, value in data.items() if key not in IGNORED_FIELDS
    }
    if isinstance(payload.get("insights"), list):
        items = []
        for item in payload["insights"]:
            if drop_service and isinstance(item, dict):
                item = {k: v for k, v in item.items() if k not in SERVICE_FIELDS}
            items.append(json.dumps(item, sort_keys=True, ensure_ascii=False))
        payload["insights"] = sorted(items)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def body_hash(data: Dict[str, Any], drop_service: bool = True) -> str:
    """SHA-256 тела insights (по умолчанию — без служебной надстройки)."""
    return hashlib.sha256(
        body_canonical(data, drop_service).encode("utf-8")
    ).hexdigest()


def service_overlay(data: Dict[str, Any]) -> Dict[str, Any]:
    """Какие служебные поля дописаны в записи и сколько записей ими помечено.

    Нужно, чтобы надстройка соседа была видна в отчёте: иначе вывод
    «идентичен» звучал бы так, будто файлы равны байт в байт.
    """
    counts: Dict[str, int] = {}
    for item in data.get("insights") or []:
        if not isinstance(item, dict):
            continue
        for field in SERVICE_FIELDS:
            if field in item:
                counts[field] = counts.get(field, 0) + 1
    records = len(data.get("insights") or [])
    return {
        "fields": counts,
        "records": records,
        "touched": sum(counts.values()),
        "clean_ratio": round(
            (records - len([1 for i in (data.get("insights") or [])
                            if isinstance(i, dict) and any(f in i for f in SERVICE_FIELDS)]))
            / records, 6) if records else 0.0,
    }


def project_paths(project: str, root: Optional[Path] = None) -> List[Path]:
    """Пути memory-файлов соседнего проекта."""
    base = (root or livingcode_root()) / project / "memory"
    return sorted(base.glob("professor_insights_cycle_*.json"))


def load_project(project: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """Загрузить и слить все файлы соседнего проекта (без канонизации).

    Отсутствующий каталог памяти — не «пустой сосед», а ошибка в данных:
    иначе отчёт об идентичности тихо выдавал бы `identical=False` для
    проекта, которого просто нет, и это читалось бы как «проекты разошлись».
    """
    paths = project_paths(project, root)
    if not paths:
        raise FileNotFoundError(
            f"у проекта {project} нет ни одного файла "
            f"professor_insights_cycle_*.json"
        )
    merged: List[Dict[str, Any]] = []
    markers: List[str] = []
    for path in project_paths(project, root):
        # `load` возвращает словарь с полями `_markers_removed`/`_source_file`;
        # распаковывать его как пару `(data, removed)` нельзя — это роняло
        # весь отчёт об идентичности на «too many values to unpack».
        data = load(path)
        markers.extend(data.get("_markers_removed") or [])
        merged.extend(data.get("insights") or [])
    return {"insights": merged, "total_insights": len(merged), "_markers_removed": markers}


def compare_pair(own: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    """Сравнить два тела инсайтов: по содержанию, побайтово и по ключам.

    Три ответа, а не один, потому что они означают разное:

    * `identical`       — содержание то же (служебная надстройка соседа
                          не считается различием). Это признак «проект —
                          копия соседа», ради которого модуль написан.
    * `byte_identical`  — файлы совпадают байт в байт.
    * `service_overlay` — какие служебные поля дописаны у соседа и в скольких
                          записях: расхождение побайтового хэша объяснено
                          конкретно, а не «ну, разные».
    """
    own_keys = set(canon([own])["keys"])
    other_keys = set(canon([other])["keys"])
    shared = own_keys & other_keys
    union = own_keys | other_keys
    overlay = service_overlay(other)
    return {
        "identical": body_hash(own) == body_hash(other),
        "byte_identical": body_hash(own, False) == body_hash(other, False),
        "own_hash": body_hash(own)[:16],
        "other_hash": body_hash(other)[:16],
        "own_byte_hash": body_hash(own, False)[:16],
        "other_byte_hash": body_hash(other, False)[:16],
        "own_records": len(own.get("insights") or []),
        "other_records": len(other.get("insights") or []),
        "own_keys": len(own_keys),
        "other_keys": len(other_keys),
        "shared_keys": len(shared),
        "jaccard": round(len(shared) / len(union), 6) if union else 0.0,
        "service_overlay": overlay,
    }


def identity_report(memory_dir: Path = DEFAULT_DIR,
                    siblings: tuple = SIBLING_PROJECTS,
                    root: Optional[Path] = None) -> Dict[str, Any]:
    """Полная картина: Project3 против каждого соседа.

    Поля результата:
      own_hash, own_records — тело Project3 целиком;
      per_sibling           — результат compare_pair по каждому соседу;
      all_identical         — True, если тело совпало со ВСЕМИ соседями
                              (признак того, что проект — копия);
      identical_siblings    — список совпавших;
      distinct_records      — сколько записей Project3 не совпало ни с одним
                              соседом (то есть действительно его собственные).
    """
    own_files = read_all(memory_dir)
    own = {
        "insights": [r for data in own_files for r in (data.get("insights") or [])],
        "total_insights": sum(len(data.get("insights") or []) for data in own_files),
    }
    per_sibling: Dict[str, Any] = {}
    foreign_keys = set()
    for project in siblings:
        try:
            other = load_project(project, root)
        except Exception as exc:  # сосед может отсутствовать или быть битым
            per_sibling[project] = {"error": str(exc)}
            continue
        result = compare_pair(own, other)
        per_sibling[project] = result
        foreign_keys |= set(canon([other])["keys"])

    own_canon = canon(own_files) if own_files else canon([own])
    own_keys = set(own_canon["keys"])
    distinct = own_keys - foreign_keys
    identical_siblings = [
        name for name, res in per_sibling.items() if res.get("identical")
    ]
    byte_identical_siblings = [
        name for name, res in per_sibling.items() if res.get("byte_identical")
    ]
    # Соседи, чьё расхождение объясняется ТОЛЬКО служебной надстройкой.
    # Их файлы не равны Project3 байт в байт, но содержание то же — значит
    # вывод «проекты разошлись» был бы неверным, а вывод «всё идентично»
    # без оговорки — вводящим в заблуждение.
    service_only = [
        name for name, res in per_sibling.items()
        if res.get("identical") and not res.get("byte_identical")
    ]
    overlay_fields: Dict[str, int] = {}
    for res in per_sibling.values():
        for field, count in (res.get("service_overlay") or {}).get("fields", {}).items():
            overlay_fields[field] = overlay_fields.get(field, 0) + count
    return {
        "own_hash": body_hash(own)[:16],
        "own_byte_hash": body_hash(own, False)[:16],
        "own_records": len(own.get("insights") or []),
        "own_keys": len(own_keys),
        "per_sibling": per_sibling,
        "all_identical": bool(identical_siblings) and len(identical_siblings) == len(per_sibling),
        "identical_siblings": identical_siblings,
        "byte_identical_siblings": byte_identical_siblings,
        "service_only_siblings": service_only,
        "service_overlay_fields": overlay_fields,
        "distinct_keys": len(distinct),
    }


def distinguish(memory_dir: Path = DEFAULT_DIR,
                siblings: tuple = SIBLING_PROJECTS,
                root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Записи Project3, которых нет ни в одном соседе (список, не число)."""
    own_files = read_all(memory_dir)
    own_canon = canon(own_files)
    foreign = set()
    for project in siblings:
        try:
            foreign |= set(canon([load_project(project, root)])["keys"])
        except Exception:
            continue
    return [
        {"key": r["_key"], "topic": r.get("topic"), "category": r.get("category")}
        for r in own_canon["records"]
        if r["_key"] not in foreign
    ]