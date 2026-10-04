"""Диагностика: какая из двух копий одной мысли богаче.

Пункт 13 проектировался на правиле «побеждает файл с ранним synced_at».
Замер `probe_winner.py` показал, что на реальных данных это закрепляет
устаревшее содержимое (все 84 проигравшие новее победителя). Прежде чем
менять правило, нужно доказать, что более свежая копия не хуже: сравниваем
поля записей парами.

Запуск: python3 tests/probe_richer.py
"""

from __future__ import annotations

import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from p1_memory.loader import iter_memory_files, load  # noqa: E402
from p1_memory.validate import dedupe_key, is_junk  # noqa: E402

COMPARE = ("summary", "relevance_score", "category", "tags", "applicable_projects", "timestamp")


def _text_len(item) -> int:
    value = item.get("summary")
    return len(value.strip()) if isinstance(value, str) else 0


def main() -> int:
    files = iter_memory_files(ROOT)
    by_key: dict[tuple, list[tuple[str, dict]]] = {}
    for path in files:
        doc = load(path)
        for item in doc.get("insights") or []:
            if is_junk(item):
                continue
            url = (item.get("source_url") or "").strip()
            if not url:
                continue
            by_key.setdefault(dedupe_key(item), []).append((path.name, item))

    pairs = [v for v in by_key.values() if len(v) > 1]
    print(f"пар-дублей: {len(pairs)}")

    longer = same = shorter = 0
    score_better = score_worse = score_same = 0
    tags_richer = tags_poorer = tags_same = 0
    identical = 0
    samples = []

    for group in pairs:
        group = sorted(group, key=lambda t: (t[1].get("timestamp") or "", t[0]))
        old_file, old = group[0]
        new_file, new = group[-1]
        if old.get("timestamp") == new.get("timestamp"):
            pass
        lo, ln = _text_len(old), _text_len(new)
        if ln > lo:
            longer += 1
        elif ln < lo:
            shorter += 1
        else:
            same += 1
        so, sn = old.get("relevance_score"), new.get("relevance_score")
        if isinstance(so, (int, float)) and isinstance(sn, (int, float)):
            if sn > so:
                score_better += 1
            elif sn < so:
                score_worse += 1
            else:
                score_same += 1
        to = len(old.get("tags") or [])
        tn = len(new.get("tags") or [])
        if tn > to:
            tags_richer += 1
        elif tn < to:
            tags_poorer += 1
        else:
            tags_same += 1
        if all(old.get(f) == new.get(f) for f in COMPARE):
            identical += 1
        if len(samples) < 3 and ln != lo:
            samples.append((group[0][0], group[-1][0], lo, ln, so, sn))

    print("\n== сравнение пар (старая запись против новой) ==")
    print(f"  summary новее длиннее: {longer}, короче: {shorter}, равно: {same}")
    print(f"  relevance_score новее выше: {score_better}, ниже: {score_worse}, равно: {score_same}")
    print(f"  тегов новее больше: {tags_richer}, меньше: {tags_poorer}, равно: {tags_same}")
    print(f"  полностью идентичных пар: {identical}")

    cat_diff = 0
    for group in pairs:
        group = sorted(group, key=lambda t: (t[1].get("timestamp") or "", t[0]))
        if group[0][1].get("category") != group[-1][1].get("category"):
            cat_diff += 1
    print(f"  расхождение category: {cat_diff}")

    print("\n== примеры ==")
    for old_file, new_file, lo, ln, so, sn in samples:
        print(f"  {old_file} (summary {lo} симв., score {so}) -> "
              f"{new_file} (summary {ln} симв., score {sn})")

    files_in_pairs = Counter(f for group in pairs for f, _ in group)
    print("\n== в каких файлах лежат пары ==", dict(files_in_pairs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())