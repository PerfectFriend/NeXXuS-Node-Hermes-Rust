"""Проба: ловит ли report --check устаревшее заявление о числе тестов.

Пишется как одноразовый воспроизводитель (правило: сначала воспроизвести,
потом чинить). Запуск: python3 tests/probe_false_ok.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from p1_memory import freshness  # noqa: E402

text = (ROOT / "MEMORY_REPORT.md").read_text(encoding="utf-8")

print("=== 1. regex _TESTS_RE на реальном отчёте ===")
print("найдено:", freshness.declared_tests(text))
for line in text.splitlines():
    if "тест" in line.lower():
        print("  строка:", line)

print()
print("=== 2. живой прогон сверки ===")
result = freshness.check_report(ROOT)
print("ok:", result["ok"])
print("расхождений по тестам:", result["test_count_mismatches"])
print("расхождений по строкам:", result["row_mismatches"])
print("тестов на диске:", result["tests_on_disk"])

print()
print("=== 3. есть ли в отчёте измеренные факты фаз 1-3 ===")
for needle in ("1835", "42", "84", "104", "124", "Харнесс", "harne", "provenance"):
    print(f"  {needle!r}: {'есть' if needle in text else 'НЕТ'}")
