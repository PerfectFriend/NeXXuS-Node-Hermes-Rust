"""Харнесс: измерение кросс-файловых дублей Project1 (2026-10-03, слот 2).

Дефект, который ищем: дедупликация в p1_memory работает ВНУТРИ одного файла,
поэтому одна и та же мысль, разложенная Профессором по разным cycle-файлам,
живёт в памяти двумя записями. Скрипт меряет это на реальных данных.

Запуск: python3 tests/harness_crossfile.py
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from p1_memory.loader import iter_memory_files, load  # noqa: E402
from p1_memory.validate import dedupe_key, is_junk  # noqa: E402


def measure(root: pathlib.Path = ROOT) -> dict:
    files = iter_memory_files(root)
    per_key: dict[tuple, set] = collections.defaultdict(set)
    topic_files: dict[str, set] = collections.defaultdict(set)
    per_file_pairs: dict[str, dict] = {}
    total = 0

    for path in files:
        doc = load(path)
        insights = doc.get("insights") or []
        total += len(insights)
        inside = collections.Counter(dedupe_key(i) for i in insights if not is_junk(i))
        per_file_pairs[path.name] = {
            "records": len(insights),
            "inside_file_dupes": sum(c - 1 for c in inside.values()),
        }
        for item in insights:
            if is_junk(item):
                continue
            per_key[dedupe_key(item)].add(path.name)
            topic_files[dedupe_key(item)[0]].add(path.name)

    cross = {k: sorted(v) for k, v in per_key.items() if len(v) > 1}
    cross_topics = {t: sorted(v) for t, v in topic_files.items() if len(v) > 1}
    surplus = sum(len(v) - 1 for v in cross.values())

    return {
        "files": [p.name for p in files],
        "records": total,
        "unique_pairs": len(per_key),
        "per_file": per_file_pairs,
        "cross_file_pairs": len(cross),
        "cross_file_surplus_records": surplus,
        "cross_file_topics": len(cross_topics),
        "sample_pairs": [list(k) for k in list(cross)[:5]],
        "sample_topics": list(cross_topics)[:5],
    }


def main() -> int:
    data = measure()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("---")
    print(f"записей: {data['records']}, уникальных (topic,url): {data['unique_pairs']}")
    print(f"кросс-файловых пар: {data['cross_file_pairs']} "
          f"(лишних записей {data['cross_file_surplus_records']})")
    print(f"тем, разложенных по файлам: {data['cross_file_topics']}")
    for name, stat in data["per_file"].items():
        print(f"  {name}: {stat['records']} записей, дублей внутри файла {stat['inside_file_dupes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())