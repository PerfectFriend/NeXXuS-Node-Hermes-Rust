"""Сверка MEMORY_REPORT.md с живым прогоном.

Дефект, который закрывает модуль: отчёт качества памяти писался вручную в
слоте 2026-10-03 и к моменту следующего слота разошёлся с фактом — заявлял
49 тестов при 104 реальных и молчал про измеренные харнессом 1835 инсайтов
и 42 дубля. Ничто этого не ловило: `report` печатал числа, а отчёт лежал
рядом и не сверялся ни с чем.

Здесь сверка машинная: числа извлекаются из markdown-таблицы отчёта и
сравниваются с тем, что даёт `p1_memory.validate.summarize` по живым данным.
Расхождение — не «сломано», а повод переписать отчёт, поэтому модуль ничего
не пишет, только перечисляет.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .loader import load
from .validate import summarize

DEFAULT_REPORT = "MEMORY_REPORT.md"

# Числа отчёта: после имени файла идут всего/мусор/дубли/чистых.
_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TOTAL_RE = re.compile(r"ИТОГО", re.IGNORECASE)
# «49 зелёных», «104 теста» и т.п.
_TESTS_RE = re.compile(r"(\d+)\s+(?:зелёных\s+)?(?:тест|теста|тестов)\b")
# Вторая форма: «тесты `tests/test_p1_memory.py` — 49 зелёных», где число
# стоит ПОСЛЕ слова «тесты». Найдена пробой tests/probe_false_ok.py на живом
# MEMORY_REPORT.md: первая регулярка её не покрывала, поэтому сверка отдавала
# exit 0 при заведомо устаревшем числе тестов.
_COUNTED_RE = re.compile(
    r"(\d+)\s+(?:зелёных|зеленых|успешных|работающих|проверок|штук)\b",
    re.IGNORECASE,
)
_TEST_WORD_RE = re.compile(r"тест", re.IGNORECASE)


def _clean_cell(cell: str) -> str:
    return cell.replace("*", "").strip()


def parse_report_table(text: str) -> Tuple[Dict[str, List[int]], Optional[List[int]]]:
    """Достать из markdown-отчёта числа по файлам и итоговую строку.

    Возвращает ({имя файла: [всего, мусор, дубли, чистых]}, итог или None).
    Строки, которые не являются таблицей, игнорируются; строка ИТОГО
    отделяется от построчных, чтобы её можно было сверять отдельно.
    """
    per_file: Dict[str, List[int]] = {}
    total: Optional[List[int]] = None
    for line in text.splitlines():
        match = _ROW_RE.match(line)
        if not match:
            continue
        cells = [_clean_cell(c) for c in match.group(1).split("|")]
        if len(cells) < 5:
            continue
        name = cells[0]
        try:
            numbers = [int(cells[i]) for i in range(1, 5)]
        except ValueError:
            continue
        if _TOTAL_RE.search(name):
            total = numbers
        elif name.endswith(".json"):
            per_file[name] = numbers
    return per_file, total


def count_tests(root: Path) -> int:
    """Сколько тестов реально собирается в tests/ (без их выполнения).

    Обнаруживает устаревшие заявления вида «49 зелёных тестов» прямо в тексте
    отчёта, не требуя запускать тесты из самого отчёта.
    """
    tests_dir = Path(root) / "tests"
    if not tests_dir.is_dir():
        return 0
    try:
        return unittest.defaultTestLoader.discover(
            str(tests_dir), pattern="test*.py", top_level_dir=str(tests_dir)
        ).countTestCases()
    except Exception:  # noqa: BLE001 — отчёт не должен падать из-за тестов
        return 0


def declared_tests(text: str) -> List[int]:
    """Все числа, которыми отчёт заявляет о количестве тестов.

    Ловит обе формы записи: «49 зелёных тестов» (число перед словом) и
    «тесты `tests/test_p1_memory.py` — 49 зелёных» (число после). Вторая
    форма раньше проскакивала молча, и сверка отчёта отдавала exit 0.
    """
    found = {int(m.group(1)) for m in _TESTS_RE.finditer(text)}
    for line in text.splitlines():
        if not _TEST_WORD_RE.search(line):
            continue
        for match in _COUNTED_RE.finditer(line):
            found.add(int(match.group(1)))
    return sorted(found)


def expected_rows(root: Path) -> Dict[str, List[int]]:
    """Живые числа по каждому memory-файлу в том же порядке, что и отчёт."""
    memory_dir = Path(root) / "memory"
    rows: Dict[str, List[int]] = {}
    if not memory_dir.is_dir():
        return rows
    for path in sorted(memory_dir.glob("professor_insights_cycle_*.json")):
        summary = summarize(load(path))
        raw = summary["raw"]
        rows[path.name] = [raw["input"], raw["junk"], raw["duplicates"], raw["kept"]]
    return rows


def check_report(root: Path, report_name: str = DEFAULT_REPORT) -> Dict[str, Any]:
    """Сверить MEMORY_REPORT.md с прогоном. Ничего не пишет."""
    root = Path(root)
    report_path = root / report_name
    result: Dict[str, Any] = {
        "report": str(report_path),
        "exists": report_path.exists(),
        "files_checked": 0,
        "files_missing_in_report": [],
        "files_unknown_to_report": [],
        "row_mismatches": [],
        "total_mismatches": [],
        "test_count_mismatches": [],
        "tests_on_disk": count_tests(root),
        "ok": False,
    }
    if not report_path.exists():
        return result

    text = report_path.read_text(encoding="utf-8")
    per_file, total = parse_report_table(text)
    live = expected_rows(root)

    result["files_missing_in_report"] = sorted(set(live) - set(per_file))
    result["files_unknown_to_report"] = sorted(set(per_file) - set(live))

    for name in sorted(set(live) & set(per_file)):
        result["files_checked"] += 1
        if live[name] != per_file[name]:
            result["row_mismatches"].append({
                "file": name,
                "report": per_file[name],
                "live": live[name],
            })

    if total is not None:
        live_total = [
            sum(v[i] for v in live.values()) for i in range(4)
        ] if live else [0, 0, 0, 0]
        if live_total != total:
            result["total_mismatches"].append({"report": total, "live": live_total})
    else:
        result["total_mismatches"].append({"report": None, "live": "строка ИТОГО не найдена"})

    actual_tests = result["tests_on_disk"]
    for declared in declared_tests(text):
        if declared != actual_tests:
            result["test_count_mismatches"].append({"report": declared, "live": actual_tests})

    result["ok"] = not (
        result["files_missing_in_report"]
        or result["files_unknown_to_report"]
        or result["row_mismatches"]
        or result["total_mismatches"]
        or result["test_count_mismatches"]
    )
    return result
