"""Печать записей, схлопывающихся в один ключ (инструмент слота)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from p3_memory.canon import record_key          # noqa: E402
from p3_memory.loader import discover, load     # noqa: E402

DEFAULT = Path(__file__).resolve().parents[1] / "memory"


def main() -> int:
    for path in sorted(discover(DEFAULT)):
        data = load(path)
        buckets = defaultdict(list)
        for record in data.get("insights") or []:
            buckets[record_key(record)].append(record)
        for key, group in buckets.items():
            if len(group) < 2:
                continue
            print(f"=== {path.name} ключ={key!r} записей={len(group)}")
            for record in group:
                print(json.dumps(record, ensure_ascii=False, indent=2)[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
