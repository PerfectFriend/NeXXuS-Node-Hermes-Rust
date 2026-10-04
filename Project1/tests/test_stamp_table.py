"""Инварианты stamp_table: итоговая строка не теряется и не уезжает.

Запуск:  cd Project1 && python3 -m unittest discover -s tests -q
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory.freshness import stamp_table  # noqa: E402

HEADER = "| Файл | Импорты | Провалы | Дубликаты | Строк |\n|---|---:|---:|---:|---:|"
ROW_A = "| a.json | 3 | 0 | 0 | 20 |"
ROW_B = "| b.json | 2 | 0 | 0 | 15 |"
TOTAL = "| **ИТОГО** | **3** | 0 | 0 | **20** |"
ROWS = {"a.json": [3, 0, 0, 20]}
B = [2, 0, 0, 15]


class TestStampTable(unittest.TestCase):
    def test_total_added_when_missing(self):
        # Отчёт без строки ИТОГО: она должна появиться после таблицы.
        out = stamp_table(f"{HEADER}\n{ROW_A}\n", ROWS)
        self.assertIn("ИТОГО", out)
        self.assertEqual(
            out.splitlines()[0], "| Файл | Импорты | Провалы | Дубликаты | Строк |"
        )

    def test_total_added_when_missing_and_rows_inserted(self):
        # Отчёт без ИТОГО и без строки b.json: обе строки должны появиться,
        # причём ИТОГО обязана завершать таблицу.
        out = stamp_table(f"{HEADER}\n{ROW_A}\n", {**ROWS, "b.json": B})
        self.assertIn(ROW_B, out)
        self.assertIn("ИТОГО", out)
        last = out.rstrip().splitlines()[-1].split("|")[1].strip().replace("*", "")
        self.assertEqual(last, "ИТОГО")

    def test_existing_total_stays_in_place(self):
        # Существующая ИТОГО остаётся на прежнем месте и в исходном оформлении.
        out = stamp_table(f"{HEADER}\n{ROW_A}\n{TOTAL}\n", ROWS)
        lines = out.splitlines()
        self.assertEqual(lines[3], TOTAL)
        self.assertEqual(len(lines), 4)

    def test_text_outside_table_untouched(self):
        text = f"# Отчёт\n\nПояснение.\n\n{HEADER}\n{ROW_A}\n\nХвост.\n"
        out = stamp_table(text, ROWS)
        self.assertTrue(out.startswith("# Отчёт\n\nПояснение.\n\n"))
        self.assertTrue(out.rstrip().endswith("Хвост."))

    def test_missing_row_inserted_before_total(self):
        out = stamp_table(f"{HEADER}\n{ROW_A}\n{TOTAL}\n", {**ROWS, "b.json": B})
        lines = out.splitlines()
        total = next(i for i, l in enumerate(lines) if "ИТОГО" in l)
        b_row = next(i for i, l in enumerate(lines) if l.startswith("| b.json"))
        self.assertLess(b_row, total)


if __name__ == "__main__":
    unittest.main()