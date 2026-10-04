"""Проба: ловит ли `report --check` расхождение чисел ВНЕ таблицы.

Дефект-кандидат фазы 4: freshness.check_report сверяет только markdown-таблицу
(всего/мусор/дубли/чистых по файлам) и число тестов. Всё остальное, что отчёт
утверждает текстом — 84 кросс-файловых дубля, 100 оставшихся, 190 входа,
provenance-факты (184 записи = [1,2,3,4], relevance 0.9) — не сверяется ни с
чем. Если такое число протухнет, отчёт молча разойдётся с прогоном.

Запуск: python3 probe_check_gap.py
"""

import re
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT1 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT1))

from p1_memory.freshness import check_report  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p1probe-"))
    root = tmp / "Project1"
    root.mkdir(parents=True)
    shutil.copytree(PROJECT1 / "memory", root / "memory")
    shutil.copytree(PROJECT1 / "tests", root / "tests")
    shutil.copy2(PROJECT1 / "MEMORY_REPORT.md", root / "MEMORY_REPORT.md")

    report = root / "MEMORY_REPORT.md"
    text = report.read_text(encoding="utf-8")

    # Портим ТОЛЬКО число вне таблицы: 84 кросс-файловых -> 7.
    patched, n = re.subn(r"84 записи повторяются", "7 записей повторяются", text)
    assert n == 1, f"подмена не сработала: {n}"
    patched = patched.replace("кросс-файловых 84", "кросс-файловых 7")
    patched = patched.replace("остаётся 100", "остаётся 77")
    report.write_text(patched, encoding="utf-8")

    result = check_report(root)
    print("отчёт с заведомо протухшими числами вне таблицы:")
    print(f"  ok = {result['ok']}")
    print(f"  row_mismatches = {result['row_mismatches']}")
    print(f"  total_mismatches = {result['total_mismatches']}")
    print(f"  test_count_mismatches = {result['test_count_mismatches']}")
    print()
    if result["ok"]:
        print("ДЕФЕКТ ПОДТВЕРЖДЁН: check даёт зелёный на протухших числах вне таблицы")
        return 1
    print("OK: расхождение поймано")
    return 0


if __name__ == "__main__":
    sys.exit(main())
