"""Проба сходимости диффа (инструмент слота, не часть пакета).

Правило проверки, которое мы хотим увидеть верным:

    removed + moved + shared == from_records
    added  + moved + shared == to_records

где ``shared`` = unchanged + changed + rewritten. Сейчас ``moved`` в
результате диффа есть, но ``shared`` его не учитывает — при ненулевом
``moved`` первое равенство не сойдётся, а читателю отчёта об этом
не сообщают.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe() -> int:
    out = subprocess.run(
        [sys.executable, "-m", "p3_memory", "diff", "--json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if out.returncode != 0:
        print("прогон не удался:", out.stderr.strip())
        return 1
    d = json.loads(out.stdout)
    shared = d["shared"]
    moved = len(d.get("moved", []))
    removed, added = len(d["removed"]), len(d["added"])
    changed, rewritten = len(d["changed"]), len(d["rewritten"])
    unchanged = d["unchanged"]

    print(f"из {d['from_records']} в {d['to_records']}")
    print(f"  shared={shared} (unchanged {unchanged} + changed {changed}"
          f" + rewritten {rewritten})")
    print(f"  added={added} removed={removed} moved={moved}")

    left = removed + moved + shared
    right = added + moved + shared
    print(f"  из старых: removed+moved+shared = {left} "
          f"(ожидалось {d['from_records']})")
    print(f"  в новых:   added+moved+shared  = {right} "
          f"(ожидалось {d['to_records']})")

    ok_old = left == d["from_records"]
    ok_new = right == d["to_records"]
    print(f"  первое равенство: {'сходится' if ok_old else 'НЕ СХОДИТСЯ'}")
    print(f"  второе равенство: {'сходится' if ok_new else 'НЕ СХОДИТСЯ'}")
    return 0 if (ok_old and ok_new) else 2


if __name__ == "__main__":
    raise SystemExit(probe())
