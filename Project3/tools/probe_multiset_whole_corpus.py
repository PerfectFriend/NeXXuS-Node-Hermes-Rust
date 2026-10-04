"""Проба целостности кратности по всему корпусу (пункт 36).

Вопрос: дубль по каноническому ключу — частный случай пары 001/1351 или
свойство всего корпуса? Если второе, то любой инструмент, считающий по
множеству ключей, теряет записи везде, а не на одной паре циклов.

Проба ничего не исправляет и ничего не пишет: только считает и печатает.
Вывод 0 — если кратность в норме, 1 — если где-то есть расхождение между
числом записей и суммой по группам (такого быть не должно: сумма всегда
равна числу записей по построению, проверка это фиксирует).
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from p3_memory import canon  # noqa: E402
from p3_memory.loader import DEFAULT_DIR, discover, load  # noqa: E402


def main(memory_dir: Path = DEFAULT_DIR) -> int:
    cycles = discover(memory_dir)
    print(f"циклов в корпусе: {len(cycles)}")
    total_records = 0
    total_groups = 0
    dup_keys: Counter = Counter()
    cycles_with_dups = 0
    worst = (0, None, 0)
    bad = []

    for path in cycles:
        data = load(path)
        records = data.get("insights") or []
        keys = Counter(canon.record_key(r) for r in records)
        total_records += len(records)
        total_groups += len(keys)
        repeated = {k: c for k, c in keys.items() if c > 1}
        if repeated:
            cycles_with_dups += 1
        for key, count in repeated.items():
            dup_keys[key] += 1
        top = max(repeated.items(), key=lambda kv: kv[1], default=(None, 0))
        if top[1] > worst[2]:
            worst = (len(repeated), path.name, top[1])
        # Сумма групп обязана равняться числу записей. Расхождение
        # означало бы, что группировка где-то теряет или удваивает запись.
        if sum(keys.values()) != len(records):
            bad.append(path.name)
        if repeated:
            shown = ", ".join(f"{k!r}×{c}" for k, c in list(repeated.items())[:3])
            print(f"  {path.name}: {len(records)} записей, "
                  f"{len(keys)} ключей, дублей {len(repeated)}; {shown}")

    print()
    print(f"всего записей: {total_records}")
    print(f"всего групп по ключу: {total_groups}")
    print(f"разница (схлопнуто кодом по множеству): {total_records - total_groups}")
    print(f"циклов с дублями: {cycles_with_dups} из {len(cycles)}")
    print(f"уникальных ключей-дублей: {len(dup_keys)}")
    if worst[0]:
        print(f"худший цикл: {worst[1]} — дублей {worst[0]}, "
              f"максимальная кратность {worst[2]}")
    if bad:
        print("РАСХОЖДЕНИЕ в сумме групп:", bad)
        return 1
    print("сумма групп равна числу записей в каждом цикле")
    return 0


if __name__ == "__main__":
    sys.exit(main())