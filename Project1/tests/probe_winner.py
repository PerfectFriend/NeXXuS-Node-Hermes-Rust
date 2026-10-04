"""Пробник пункта 13: какой файл побеждает и не выбирается ли устаревшее содержимое.

Project2 в этом же слоте обнаружил инверсию: номер цикла в имени файла НЕ дата,
`cycle_1351.json` записан раньше `cycle_001.json`, и более новое содержимое лежит
в `cycle_001`. Если победителя выбирать по synced_at/имени, дедупликация может
закрепить устаревшую копию мысли. Здесь меряем это прямо на данных Project1.

Запуск: python3 tests/probe_winner.py
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from p1_memory.crossfile import plan_crossfile  # noqa: E402
from p1_memory.loader import iter_memory_files, load  # noqa: E402
from p1_memory.validate import dedupe_key, is_junk  # noqa: E402


def main() -> int:
    files = iter_memory_files(ROOT)
    pairs = [(p, load(p)) for p in files]

    print("== файлы памяти ==")
    for p, doc in sorted(pairs, key=lambda t: t[0].name):
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
        recs = doc.get("insights") or []
        stamps = [i.get("timestamp") or "" for i in recs]
        newest = max((s for s in stamps if s), default="—")
        print(f"  {p.name}: synced_at={doc.get('synced_at')!r} записей={len(recs)} "
              f"mtime={mtime.isoformat(timespec='seconds')} newest_timestamp={newest!r}")

    plan, stats = plan_crossfile(pairs)
    print("\n== план (порядок = порядок победы) ==")
    for e in plan:
        print(f"  {e['path'].name}: kept={e['stats']['kept']} cross={e['dropped_cross']}")
    print("  totals:", json.dumps(stats, ensure_ascii=False))

    # Свежесть выигравшей записи против проигравшей для каждой схлопнутой пары.
    kept_by_key = {}
    for e in plan:
        for item in e["kept"]:
            if not is_junk(item) and (item.get("source_url") or "").strip():
                kept_by_key.setdefault(dedupe_key(item), (e["path"].name, item))

    losers_newer = 0
    equal_ts = 0
    checked = 0
    for e in plan:
        loser_keys = {dedupe_key(i) for i in e["doc"].get("insights") or []
                      if not is_junk(i) and (i.get("source_url") or "").strip()}
        for item in e["doc"].get("insights") or []:
            if is_junk(item):
                continue
            url = (item.get("source_url") or "").strip()
            if not url:
                continue
            key = dedupe_key(item)
            win = kept_by_key.get(key)
            if not win or win[0] == e["path"].name:
                continue
            checked += 1
            win_ts = win[1].get("timestamp") or ""
            lose_ts = item.get("timestamp") or ""
            if not win_ts or not lose_ts:
                continue
            if win_ts == lose_ts:
                equal_ts += 1
            elif lose_ts > win_ts:
                losers_newer += 1

    print("\n== контроль победителя на датах ==")
    print(f"  схлопнутых пар с двумя датами: {checked}")
    print(f"  проигравшая НОВЕЕ победителя (порча свежести): {losers_newer}")
    print(f"  даты равны (выбор по имени/порядку): {equal_ts}")

    # Проверка идемпотентности: второй проход не должен ничего менять.
    again = plan_crossfile([(e["path"], {"synced_at": e["doc"].get("synced_at"),
                                          "insights": e["kept"]}) for e in plan])
    print("\n== идемпотентность ==")
    print("  stats повторного прохода:", json.dumps(again[1], ensure_ascii=False))
    print("  url-ключи победителей:",
          len({dedupe_key(v[1]) for v in kept_by_key.values()}))
    c = Counter(dedupe_key(i) for _, i in
                [(e["path"].name, it) for e in plan for it in e["kept"]])
    print("  записей в плане:", sum(c.values()), "уникальных ключей:", len(c))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())