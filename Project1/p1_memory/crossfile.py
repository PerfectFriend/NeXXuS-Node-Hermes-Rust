"""Кросс-файловая дедупликация памяти Project1.

Дефект, который закрывает модуль: `validate.clean_insights` дедуплицирует
записи ВНУТРИ одного файла. Профессор, однако, раскладывает одну и ту же мысль
по нескольким cycle-файлам, поэтому память разрастается копиями. Замер
(`tests/harness_crossfile.py`, 2026-10-03): 190 записей, 100 уникальных пар
`(topic, source_url)`, 84 пары присутствуют сразу в двух файлах — при нулевом
числе дублей внутри файлов.

Правило выбора победителя (исправлено 2026-10-03, слот 3):

    1. Побеждает запись с более поздним `timestamp`.
    2. При равных timestamp'ах — файл с более ранним `synced_at`.
    3. При равных synced_at — имя файла (меньшее вперёд).
    4. При равенстве и того, и другого — позиция в файле.

Первый пункт добавлен после замера `tests/probe_winner.py`: номер цикла в
имени файла НЕ дата (`cycle_1351.json` записан 14 августа, `cycle_001.json` —
16 августа), а правило «побеждает файл с ранним synced_at» закрепляло
устаревшее содержимое — все 84 схлопнутые записи оказались новее оставленных.
Это тот же класс инверсии, что Project2 зафиксировал в своих данных.

Записи без `source_url` не сливаются НИКОГДА: без ссылки тождество мысли не
доказано, объединять их значит терять данные.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

from .validate import clean_insights, dedupe_key

class _Str:
    """Строка, которая тем больше, чем меньше исходная (для сортировки max)."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Str) and other.value == self.value

    def __lt__(self, other: "_Str") -> bool:
        # Обратное сравнение исходных строк.
        return self.value > other.value

    def __repr__(self) -> str:  # pragma: no cover - только для отладки
        return f"_Str({self.value!r})"


# (timestamp записи, обратный synced_at, обратное имя файла, позиция)
Winner = Tuple[str, "_Str", "_Str", int]


def _freshness(item: Dict[str, Any], synced_at: str, name: str, index: int) -> Winner:
    """Ключ ранжирования кандидатов: свежесть записи, затем детерминированные поля.

    Второй уровень инвертирован через `_Str`: при равных timestamp'ах важен
    более ранний файл, а сравнение выше идёт по максимуму.
    """
    stamp = item.get("timestamp")
    stamp = stamp if isinstance(stamp, str) else ""
    return (stamp, _Str(synced_at or ""), _Str(name), -index)


def _mergeable(item: Dict[str, Any]) -> bool:
    """Схлопывать запись с записью из другого файла можно только с source_url."""
    url = item.get("source_url")
    return isinstance(url, str) and url.strip() != ""


def plan_crossfile(
    docs: Sequence[Tuple[Path, Dict[str, Any]]]
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Разложить записи по файлам без кросс-файловых дублей.

    Возвращает (план, счётчики). План — ровно один элемент на каждый файл:
    {path, doc, kept, dropped_cross, stats}. Это нужно и CLI (полный отчёт по
    каждому файлу), и тестам, сверяющим `stats["files"]` с числом файлов.

    Победителем каждой пары становится самая свежая запись; остальные копии
    уходят в `dropped_cross`, оставаясь в своём файле.
    """
    file_stats: Dict[str, Dict[str, int]] = {}
    payload: Dict[str, Dict[str, Any]] = {}
    totals = {"files": len(docs), "input": 0, "junk": 0,
              "duplicates_inside": 0, "cross_file_duplicates": 0, "kept": 0}

    # Шаг 1: внутрифайловая очистка и сбор кандидатов по ключу.
    best: Dict[Tuple[str, str], Tuple[Winner, str]] = {}
    for path, doc in docs:
        name = path.name
        synced_at = doc.get("synced_at")
        synced_at = synced_at if isinstance(synced_at, str) else ""
        kept, stats = clean_insights(doc.get("insights") or [])
        payload[name] = {"path": path, "doc": doc, "synced_at": synced_at, "kept": kept}
        file_stats[name] = {"input": stats["input"], "junk": stats["junk"],
                             "duplicates": stats["duplicates"], "cross": 0,
                             "kept": len(kept)}
        totals["input"] += stats["input"]
        totals["junk"] += stats["junk"]
        totals["duplicates_inside"] += stats["duplicates"]

        for index, item in enumerate(kept):
            if not _mergeable(item):
                continue
            rank = _freshness(item, synced_at, name, index)
            key = dedupe_key(item)
            current = best.get(key)
            if current is None or rank > current[0]:
                best[key] = (rank, name)

    # Шаг 2: оставить в каждом файле только победителей его пар.
    plan: List[Dict[str, Any]] = []
    for name in sorted(payload):
        entry = payload[name]
        kept: List[Dict[str, Any]] = []
        dropped = 0
        for item in entry["kept"]:
            if _mergeable(item):
                winner = best[dedupe_key(item)][1]
                if winner != name:
                    dropped += 1
                    continue
            kept.append(item)
        file_stats[name]["cross"] = dropped
        file_stats[name]["kept"] = len(kept)
        totals["cross_file_duplicates"] += dropped
        totals["kept"] += len(kept)
        plan.append({"path": entry["path"], "doc": entry["doc"], "kept": kept,
                     "dropped_cross": dropped, "stats": file_stats[name]})
    return plan, totals


def count_crossfile(docs: Sequence[Tuple[Path, Dict[str, Any]]]) -> int:
    """Только измерение, без записи: сколько дублей уходит при --scope all."""
    _, stats = plan_crossfile(docs)
    return int(stats["cross_file_duplicates"])


def merged_view(docs: Sequence[Tuple[Path, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Плоский список уникальных записей после кросс-файловой очистки.

    Порядок — по имени файла, внутри файла порядок исходный: так список
    повторяем при любом порядке перебора на входе.
    """
    plan, _ = plan_crossfile(docs)
    result: List[Dict[str, Any]] = []
    for entry in sorted(plan, key=lambda e: e["path"].name):
        result.extend(entry["kept"])
    return result


__all__ = ["plan_crossfile", "count_crossfile", "merged_view"]