"""Диагностика формы живых файлов памяти Project1.

Показывает: сколько записей, сколько уникальных пар (topic, source_url),
и какие поля реально присутствуют в записях.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory.loader import load  # noqa: E402

FILES = [
    "memory/professor_insights_cycle_001.json",
    "memory/professor_insights_cycle_1351.json",
]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    for name in FILES:
        data = load(root / name)
        insights = data.get("insights") or []
        pairs = collections.Counter(
            (i.get("topic"), i.get("source_url")) for i in insights
        )
        print(f"{name}: записей {len(insights)}, синхронизировано {data.get('synced_at')}")
        print(f"  уникальных пар (topic, source_url): {len(pairs)}")
        for pair, count in pairs.most_common(3):
            print(f"    x{count} {pair}")
        fields = collections.Counter()
        for item in insights:
            for key in item:
                fields[key] += 1
        print("  поля: " + json.dumps(dict(fields.most_common()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())