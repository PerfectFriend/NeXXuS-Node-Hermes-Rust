"""Независимый пересчёт shared/rewritten по кратностям (инструмент слота).

Цель — проверить, что 86, а не 85: 85 получалось, когда один из трёх
экземпляров ключа ``unknown|ai engineering|`` в цикле 1351 затирал
двух других. Пересчёт ведём от сырых файлов, не зовём ``diff_cycles``.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from p3_memory import canon  # noqa: E402
from p3_memory.loader import DEFAULT_DIR, load  # noqa: E402


def recount(memory_dir: Path) -> int:
    data_from = load(memory_dir / "professor_insights_cycle_001.json")
    data_to = load(memory_dir / "professor_insights_cycle_1351.json")
    old = Counter(canon.record_key(r) for r in data_from["insights"])
    new = Counter(canon.record_key(r) for r in data_to["insights"])
    shared = sum(min(count, new[key]) for key, count in old.items())
    print(f"из {len(data_from['insights'])} в {len(data_to['insights'])}")
    print(f"общих по кратности: {shared}")
    print(f"общих по множеству: {len(set(old) & set(new))} ← то, что считал старый код")
    print(f"уникальных ключей: {len(set(old))} и {len(set(new))}")
    return shared


if __name__ == "__main__":
    recount(DEFAULT_DIR)