"""Диагностика: сколько записей-мусора и сколько совпадающих summary.

Проверяет, не осталось ли внутрифайловых дублей, которые не ловятся ключом
(topic, source_url), потому что url или тема различаются, а смысл один.
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


def norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    for name in FILES:
        data = load(root / name)
        insights = data.get("insights") or []
        by_summary = collections.defaultdict(set)
        junk = 0
        for item in insights:
            if not item.get("topic") or not item.get("source_url"):
                junk += 1
            by_summary[norm(item.get("summary"))].add(
                (item.get("topic"), item.get("source_url"))
            )
        multi = {s: v for s, v in by_summary.items() if len(v) > 1}
        print(f"{name}: записей {len(insights)}, без темы или url {junk}")
        print(f"  разных summary: {len(by_summary)}, summary с несколькими (topic,url): {len(multi)}")
        for summary, variants in list(multi.items())[:3]:
            print(f"    summary: {summary[:70]!r}")
            print(f"      варианты: {json.dumps(sorted(map(list, variants)), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())