"""Разбор дубля `unknown|ai engineering|` (пункт 36, вторая часть).

Проба целостности показала: дубль ровно один ключ, `unknown|ai
engineering|`, и кратность 2 в цикле 001 и 3 в 1351. Прежде чем считать
это потерей кратности, надо убедиться, что это действительно одинаковые
записи, а не разные записи с пустым URL, случайно получившие один ключ.

Если поля кроме ключа различаются — перед нами три разные записи,
схлопывать которые нельзя тем более, и дедупликация по ключу сама по
себе бессмысленна для этого класса записей: надо либо включить
дискриминатор, либо честно признать, что записи равны.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from p3_memory import canon  # noqa: E402
from p3_memory.loader import DEFAULT_DIR, load  # noqa: E402

TARGET = "unknown|ai engineering|"


def dump(path: Path) -> None:
    data = load(path)
    records = [r for r in (data.get("insights") or [])
               if canon.record_key(r) == TARGET]
    print(f"=== {path.name}: {len(records)} записей с таким ключом ===")
    for i, record in enumerate(records, 1):
        print(f"  [{i}] {json.dumps(record, ensure_ascii=False, sort_keys=True)}")


def main(memory_dir: Path = DEFAULT_DIR) -> int:
    for name in ("professor_insights_cycle_001.json",
                 "professor_insights_cycle_1351.json"):
        path = memory_dir / name
        dump(path)

    a = load(memory_dir / "professor_insights_cycle_001.json")
    b = load(memory_dir / "professor_insights_cycle_1351.json")
    ra = [r for r in a["insights"] if canon.record_key(r) == TARGET]
    rb = [r for r in b["insights"] if canon.record_key(r) == TARGET]

    # Сравниваем как мультимножества полных записей: если два экземпляра
    # совпадают целиком, это дубль; если нет — разные записи под одним ключом.
    ca = Counter(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in ra)
    cb = Counter(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rb)
    print()
    print(f"001: {len(ra)} записей, уникальных по всем полям: {len(ca)}")
    print(f"1351: {len(rb)} записей, уникальных по всем полям: {len(cb)}")
    for label, counts in (("001", ca), ("1351", cb)):
        dups = {k: v for k, v in counts.items() if v > 1}
        if dups:
            print(f"{label}: полных дублей {len(dups)} → {list(dups.values())}")
        else:
            print(f"{label}: полных дублей нет — записи различаются полями")

    if len(ca) == len(ra) and len(cb) == len(rb):
        print()
        print("ВЫВОД: записи под одним ключом РАЗНЫЕ. Схлопывать их нельзя:")
        print("ключ недостаточен как идентификатор, нужна правка канона.")
        return 0
    print()
    print("ВЫВОД: записи под одним ключом идентичны — честный дубль,")
    print("кратность хранить нужно, и код теперь это делает.")
    return 0


if __name__ == "__main__":
    sys.exit(main())