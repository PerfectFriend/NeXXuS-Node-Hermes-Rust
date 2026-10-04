"""Замер для пункта 15 плана: сколько ключей (topic, source_url) схлопывается
после нормализации URL-кодирования.

Предположение плана: в данных есть и `Dataview%20Mastery.md`, и
`Dataview Mastery.md`. Этот скрипт проверяет, так ли это, и даёт число
слитых ключей — с отчётом, а не на веру.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory.loader import iter_memory_files, load
from p1_memory.validate import dedupe_key, is_junk

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    groups: dict = defaultdict(list)
    total = 0
    for path in iter_memory_files(ROOT):
        doc = load(path)
        for item in doc.get("insights") or []:
            if is_junk(item):
                continue
            total += 1
            key = dedupe_key(item)
            norm = (key[0], unquote(key[1]))
            groups[norm].append((path.name, key[1]))

    merged = {k: v for k, v in groups.items() if len({url for _, url in v}) > 1}
    raw_keys = {dedupe_key(i)[1] for p in iter_memory_files(ROOT)
                for i in (load(p).get("insights") or []) if not is_junk(i)}

    print(f"живых записей: {total}")
    print(f"уникальных сырых URL: {len(raw_keys)}")
    print(f"уникальных нормализованных пар (topic,url): {len(groups)}")
    print(f"групп, где один URL имеет несколько написаний: {len(merged)}")
    for key, variants in list(merged.items())[:10]:
        print("  ", key[0][:40], "->", sorted({u for _, u in variants}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())