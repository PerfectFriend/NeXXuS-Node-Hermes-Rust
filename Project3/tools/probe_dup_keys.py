"""Диагностика: почему дифф не сходится по количеству (инструмент слота).

Печатает для каждого цикла: сколько записей в файле, сколько уникальных
ключей `canon.record_key`, и какие записи делят ключ попарно.
"""
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
        records = data.get("insights") or []
        buckets = defaultdict(list)
        for record in records:
            buckets[record_key(record)].append(record)
        dupes = {k: v for k, v in buckets.items() if len(v) > 1}
        print(f"{path.name}: записей {len(records)}, "
              f"уникальных ключей {len(buckets)}, дублей ключей {len(dupes)}")
        for key, group in dupes.items():
            print(f"  КЛЮЧ {key}")
            for record in group:
                print(f"    - id={record.get('id')!r} "
                      f"ts={record.get('timestamp')!r} "
                      f"cat={record.get('category')!r} "
                      f"url={str(record.get('source_url'))[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
