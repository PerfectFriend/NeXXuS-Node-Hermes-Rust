"""Аудит происхождения инсайтов Project1.

Вопрос, который память Project1 не давала ответа: откуда приходят записи и
различают ли они проекты. Измерено на живых данных (2 файла, 190 инсайтов):
- 184 записи `source_type=textbook`, 6 — `ai_eng_daily`;
- у **всех** 190 записей `applicable_projects = [1,2,3,4]`, то есть поле
  не различает проекты вовсе, хотя именно по нему `professor_sync.py`
  отбирает память для каждого из Project1–4 (см. HOTCODE_NOTES);
- `relevance_score` принимает ровно два значения: 0.7 и 0.9.

Модуль ничего не исправляет — он превращает эти предположения в числа,
которые можно закоммитить и проверить тестом. Различительность
`applicable_projects` считается отдельной метрикой: доля уникальных наборов
проектов и число записей, не уникальных для Project1.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from . import VALID_PROJECTS
from .loader import iter_memory_files, load
from .validate import is_junk

JUNK_LABEL = "<мусор>"


def _label(value: Any) -> str:
    if value is None:
        return "<нет>"
    if isinstance(value, str):
        text = value.strip()
        return text if text else "<пусто>"
    return str(value)


def audit(root: Path, project: int = 1) -> Dict[str, Any]:
    """Сводка происхождения по всей памяти проекта."""
    root = Path(root)
    files = iter_memory_files(root)
    rows: List[Dict[str, Any]] = []
    source_type: Counter = Counter()
    category: Counter = Counter()
    scores: Counter = Counter()
    project_sets: Counter = Counter()
    total = 0
    junk = 0
    no_url = 0
    no_tags = 0
    no_timestamp = 0

    for path in files:
        doc = load(path)
        insights = doc.get("insights") or []
        file_rows: List[Dict[str, Any]] = []
        for index, item in enumerate(insights):
            total += 1
            if is_junk(item):
                junk += 1
                source_type[JUNK_LABEL] += 1
                category[JUNK_LABEL] += 1
                file_rows.append({"index": index, "topic": JUNK_LABEL, "junk": True})
                continue
            st = item.get("source_type")
            cat = item.get("category")
            source_type[_label(st)] += 1
            category[_label(cat)] += 1
            scores[_label(item.get("relevance_score"))] += 1
            projects = item.get("applicable_projects")
            key = tuple(sorted(projects)) if isinstance(projects, list) else ()
            project_sets[key] += 1
            if not isinstance(item.get("source_url"), str) or not item.get("source_url", "").strip():
                no_url += 1
            if not isinstance(item.get("tags"), list) or not item.get("tags"):
                no_tags += 1
            if not isinstance(item.get("timestamp"), str) or not item.get("timestamp", "").strip():
                no_timestamp += 1
            file_rows.append({
                "index": index,
                "topic": _label(item.get("topic")),
                "source_type": _label(st),
                "category": _label(cat),
                "relevance_score": item.get("relevance_score"),
                "applicable_projects": list(key),
                "has_url": bool(isinstance(item.get("source_url"), str) and item["source_url"].strip()),
                "tags": len(item.get("tags") or []) if isinstance(item.get("tags"), list) else 0,
            })
        rows.append({
            "file": path.name,
            "cycle": doc.get("cycle"),
            "synced_at": doc.get("synced_at", ""),
            "insights": len(insights),
            "rows": file_rows,
        })

    all_projects = tuple(sorted(VALID_PROJECTS))
    uniform = project_sets.get(all_projects, 0)
    unique_sets = len(project_sets)
    # Поле различает проекты, если хотя бы одна запись помечена не всеми
    # проектами сразу. Единственный набор «все проекты» различения не даёт.
    non_uniform = sum(n for key, n in project_sets.items() if key != all_projects)
    discriminates = non_uniform > 0
    selects_for_project = sum(
        n for key, n in project_sets.items() if project in key
    )
    useless_for_project = uniform if not discriminates else 0

    return {
        "root": str(root),
        "project": project,
        "files": len(files),
        "total": total,
        "junk": junk,
        "clean": total - junk,
        "no_source_url": no_url,
        "no_tags": no_tags,
        "no_timestamp": no_timestamp,
        "source_type": dict(source_type),
        "category": dict(category),
        "relevance_score": dict(scores),
        "applicable_projects": {
            "sets": {str(list(k)): v for k, v in project_sets.items()},
            "unique_sets": unique_sets,
            "uniform_all_projects": uniform,
            "uniform_share": round(uniform / total, 4) if total else 0.0,
            "discriminates": discriminates,
            "selects_for_project": selects_for_project,
            "useless_for_selection": useless_for_project,
        },
        "detail": rows,
    }
