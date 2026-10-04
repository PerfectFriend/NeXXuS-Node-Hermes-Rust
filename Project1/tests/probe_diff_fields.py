"""Диагностика: в каком именно поле расходятся пары-дубли.

probe_richer.py показал: summary, relevance_score, tags, category у всех 84
пар совпадают, но пары не идентичны целиком. Значит расходится другое поле —
именно его нужно знать, прежде чем объявлять копии взаимозаменяемыми.

Запуск: python3 tests/probe_diff_fields.py
"""

from __future__ import annotations

import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from p1_memory.loader import iter_memory_files, load  # noqa: E402
from p1_memory.validate import dedupe_key, is_junk  # noqa: E402


def main() -> int:
    files = iter_memory_files(ROOT)
    by_key: dict[tuple, list[tuple[str, dict]]] = {}
    for path in files:
        doc = load(path)
        for item in doc.get("insights") or []:
            if is_junk(item):
                continue
            if not (item.get("source_url") or "").strip():
                continue
            by_key.setdefault(dedupe_key(item), []).append((path.name, item))

    pairs = [v for v in by_key.values() if len(v) > 1]
    field_diff = Counter()
    sample = None

    for group in pairs:
        group = sorted(group, key=lambda t: (t[1].get("timestamp") or "", t[0]))
        old, new = group[0][1], group[-1][1]
        keys = set(old) | set(new)
        diffs = sorted(k for k in keys if old.get(k) != new.get(k))
        for k in diffs:
            field_diff[k] += 1
        if sample is None and diffs:
            sample = (group[0][0], group[-1][0], diffs, old, new)

    print(f"пар-дублей: {len(pairs)}")
    print("\n== поля, по которым расходятся пары ==")
    for field, count in field_diff.most_common():
        print(f"  {field}: {count}")

    if sample:
        old_file, new_file, diffs, old, new = sample
        print(f"\n== пример: {old_file} vs {new_file} ==")
        for field in diffs:
            print(f"  {field}:")
            print(f"    старше: {old.get(field)!r}")
            print(f"    новее : {new.get(field)!r}")

    # Тот ли это timestamp у всех пар: если да, поле объясняет всю выборку.
    only_ts = sum(1 for g in pairs
                  if sorted(g, key=lambda t: (t[1].get("timestamp") or "", t[0]))
                  and set(g[0][1]) | set(g[-1][1])
                  and [k for k in (set(g[0][1]) | set(g[-1][1]))
                       if g[0][1].get(k) != g[-1][1].get(k)] == ["timestamp"])
    print(f"\nпар, различающихся ТОЛЬКО по timestamp: {only_ts} из {len(pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())