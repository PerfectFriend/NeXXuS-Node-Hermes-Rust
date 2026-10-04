#!/usr/bin/env python3
"""Проба диагностики `report --check` (пункт 39 плана).

Показывает, что проверка свежести отчёта не молчит о расхождении.
До правки кода два разных случая — повтор существующей строки и
перестановка двух строк — давали ОДИН И ТОТ ЖИ пустой ответ при
`ok=False`, то есть CLI сообщал «устарел» и не называл ничего.

Проба ничего не оставляет на диске: исходный текст отчёта восстанавливается
в `finally`. Код возврата 1, если хоть один случай назван плохо, — чтобы
проба годилась и как страж.

Запуск: python3 tools/probe_report_diagnosis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p3_memory.report import check_report, report_path  # noqa: E402


def _line_starts_with(lines: list[str], prefix: str) -> int:
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index
    raise SystemExit(f"в отчёте нет строки, начинающейся с {prefix!r}")


def main() -> int:
    target = report_path()
    original = target.read_text(encoding="utf-8")
    lines = original.splitlines()
    first_row = _line_starts_with(lines, "| добавлено")
    swapped = list(lines)
    swapped[first_row], swapped[first_row + 1] = (
        swapped[first_row + 1], swapped[first_row])

    cases = [
        ("эталон", original, True),
        ("лишняя новая строка",
         "\n".join(lines + ["СТРОКА-КОТОРОЙ-НЕ-БЫЛО"]) + "\n", False),
        ("повтор существующей строки",
         "\n".join(lines + [lines[first_row]]) + "\n", False),
        ("перестановка двух строк",
         "\n".join(swapped) + "\n", False),
        ("нет завершающего перевода строки", original.rstrip("\n"), False),
    ]

    failures = 0
    try:
        for name, text, expect_ok in cases:
            target.write_text(text, encoding="utf-8")
            result = check_report(target)
            named = (result["missing_lines"] or result["extra_lines"]
                     or result.get("difference"))
            verdict = "хорошо" if result["ok"] == expect_ok and (
                expect_ok or named) else "ПЛОХО"
            if verdict == "ПЛОХО":
                failures += 1
            print(f"[{verdict}] {name}: ok={result['ok']}")
            if expect_ok and result["ok"]:
                # Совпадение — расхождения нет, и «ничего не названо»
                # здесь правильный вывод, а не признак поломки. Печатать
                # про него нельзя: строка выглядела бы как диагноз.
                print("    совпадает с build_report()")
                continue
            if result.get("difference"):
                diff = result["difference"]
                print(f"    вид={diff['kind']} строка={diff['line']} "
                      f"колонка={diff['column']}")
                print(f"    ожидалось: {diff['expected_here']}")
                print(f"    в файле:   {diff['actual_here']}")
            elif result["missing_lines"] or result["extra_lines"]:
                for line in (result["missing_lines"]
                             + result["extra_lines"])[:3]:
                    print(f"    строка: {line}")
            else:
                print("    НИЧЕГО НЕ НАЗВАНО — расхождение не диагностировано")
    finally:
        target.write_text(original, encoding="utf-8")

    restored = check_report(target)["ok"]
    print(f"\nфайл восстановлен: {restored}")
    if not restored:
        failures += 1
    print(f"итог: {'все случаи названы' if not failures else failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())