"""Тесты сверки отчёта (freshness) и аудита происхождения (provenance).

Запуск:  cd Project1 && python3 -m unittest discover -s tests -q
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory import freshness, loader, provenance  # noqa: E402
from p1_memory.cli import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def good_insight(**over):
    base = {
        "topic": "Graph Engineering Fundamentals",
        "category": "Textbook",
        "summary": "Краткое изложение темы",
        "source_url": "https://example.org/a.md",
        "source_type": "textbook",
        "relevance_score": 0.9,
        "applicable_projects": [1, 2, 3, 4],
        "tags": ["learned"],
        "timestamp": "2026-08-16T08:10:33+00:00",
    }
    base.update(over)
    return base


def document(insights, **over):
    doc = {
        "cycle": 1,
        "project": 1,
        "synced_at": "2026-08-16T08:10:33+00:00",
        "insights": insights,
        "total_insights": len(insights),
    }
    doc.update(over)
    return doc


class TempProject:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="p1fresh-"))
        (self.root / "memory").mkdir()
        (self.root / "tests").mkdir()

    def write_memory(self, name, data):
        path = self.root / "memory" / name
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_report(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def write_test(self, name="test_dummy.py"):
        path = self.root / "tests" / name
        path.write_text(
            "import unittest\n\n\nclass TestDummy(unittest.TestCase):\n"
            "    def test_nothing(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        return path

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestParseReportTable(unittest.TestCase):
    def test_reads_rows_and_total(self):
        text = (
            "| файл | всего | мусор | дубли | чистых |\n"
            "|---|---|---|---|---|\n"
            "| a.json | 10 | 2 | 1 | 7 |\n"
            "| **ИТОГО** | 10 | 2 | 1 | 7 |\n"
        )
        per_file, total = freshness.parse_report_table(text)
        self.assertEqual(per_file, {"a.json": [10, 2, 1, 7]})
        self.assertEqual(total, [10, 2, 1, 7])

    def test_ignores_non_table_lines(self):
        per_file, total = freshness.parse_report_table("отчёт без таблиц\n\nтекст\n")
        self.assertEqual(per_file, {})
        self.assertIsNone(total)


class TestCheckReport(unittest.TestCase):
    def setUp(self):
        self.tmp = TempProject()

    def tearDown(self):
        self.tmp.cleanup()

    def test_matching_report_is_ok(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight(), good_insight(topic="Другая")]))
        self.tmp.write_test()
        self.tmp.write_report("MEMORY_REPORT.md", (
            "| файл | всего | мусор | дубли | чистых |\n"
            "|---|---|---|---|---|\n"
            "| professor_insights_cycle_001.json | 2 | 0 | 0 | 2 |\n"
            "| ИТОГО | 2 | 0 | 0 | 2 |\n"
            "\nСобрано 1 тест.\n"
        ))
        result = freshness.check_report(self.tmp.root)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["exists"])
        self.assertEqual(result["files_checked"], 1)

    def test_stale_row_is_reported(self):
        self.tmp.write_memory("professor_insights_cycle_001.json", document([good_insight()]))
        self.tmp.write_report("MEMORY_REPORT.md", (
            "| файл | всего | мусор | дубли | чистых |\n"
            "|---|---|---|---|---|\n"
            "| professor_insights_cycle_001.json | 99 | 0 | 0 | 99 |\n"
            "| ИТОГО | 99 | 0 | 0 | 99 |\n"
        ))
        result = freshness.check_report(self.tmp.root)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["row_mismatches"]), 1)
        self.assertEqual(result["row_mismatches"][0]["live"], [1, 0, 0, 1])

    def test_stale_test_claim_is_reported(self):
        self.tmp.write_report("MEMORY_REPORT.md", "Собрано 49 зелёных тестов.\n")
        result = freshness.check_report(self.tmp.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["test_count_mismatches"][0]["report"], 49)

    def test_missing_report_is_not_ok_but_not_crash(self):
        result = freshness.check_report(self.tmp.root)
        self.assertFalse(result["exists"])
        self.assertFalse(result["ok"])

    def test_check_is_read_only(self):
        self.tmp.write_memory("professor_insights_cycle_001.json", document([good_insight()]))
        report = self.tmp.write_report("MEMORY_REPORT.md", "пусто\n")
        before = report.read_text(encoding="utf-8")
        freshness.check_report(self.tmp.root)
        self.assertEqual(report.read_text(encoding="utf-8"), before)


class TestIterMemoryFilesByTime(unittest.TestCase):
    def setUp(self):
        self.tmp = TempProject()

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_file_first(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight()], cycle=1,
                                       synced_at="2026-08-14T05:29:02+00:00"))
        self.tmp.write_memory("professor_insights_cycle_1351.json",
                              document([good_insight()], cycle=1351,
                                       synced_at="2026-08-16T08:10:33+00:00"))
        names = [p.name for p in loader.iter_memory_files(self.tmp.root, by_time=True)]
        self.assertEqual(names[0], "professor_insights_cycle_1351.json")

    def test_default_order_is_by_name(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight()], synced_at="2026-08-14T05:29:02+00:00"))
        self.tmp.write_memory("professor_insights_cycle_1351.json",
                              document([good_insight()], synced_at="2026-08-16T08:10:33+00:00"))
        names = [p.name for p in loader.iter_memory_files(self.tmp.root)]
        self.assertEqual(names, ["professor_insights_cycle_001.json",
                                 "professor_insights_cycle_1351.json"])

    def test_unreadable_synced_at_goes_last(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight()], synced_at="не дата"))
        self.tmp.write_memory("professor_insights_cycle_1351.json",
                              document([good_insight()], synced_at="2026-08-16T08:10:33+00:00"))
        names = [p.name for p in loader.iter_memory_files(self.tmp.root, by_time=True)]
        self.assertEqual(names[-1], "professor_insights_cycle_001.json")

    def test_naive_and_aware_timestamps_do_not_crash(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight()], synced_at="2026-08-16T08:10:33"))
        self.tmp.write_memory("professor_insights_cycle_1351.json",
                              document([good_insight()], synced_at="2026-08-16T08:10:33+00:00"))
        names = [p.name for p in loader.iter_memory_files(self.tmp.root, by_time=True)]
        self.assertEqual(len(names), 2)


class TestProvenanceAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = TempProject()

    def tearDown(self):
        self.tmp.cleanup()

    def test_uniform_projects_are_useless_for_selection(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight(), good_insight(topic="Б")]))
        audit = provenance.audit(self.tmp.root, project=1)
        self.assertEqual(audit["total"], 2)
        self.assertEqual(audit["clean"], 2)
        self.assertEqual(audit["applicable_projects"]["unique_sets"], 1)
        self.assertFalse(audit["applicable_projects"]["discriminates"])
        self.assertTrue(audit["applicable_projects"]["useless_for_selection"])

    def test_project_specific_insight_is_selected(self):
        self.tmp.write_memory("professor_insights_cycle_001.json",
                              document([good_insight(applicable_projects=[2, 3])]))
        audit = provenance.audit(self.tmp.root, project=1)
        self.assertTrue(audit["applicable_projects"]["discriminates"])
        self.assertFalse(audit["applicable_projects"]["useless_for_selection"])
        self.assertEqual(audit["applicable_projects"]["selects_for_project"], 0)

    def test_missing_provenance_is_counted(self):
        self.tmp.write_memory("professor_insights_cycle_001.json", document([{
            "topic": "Без provenance", "category": "Textbook", "summary": "x",
        }]))
        audit = provenance.audit(self.tmp.root, project=1)
        self.assertEqual(audit["no_tags"], 1)
        self.assertEqual(audit["no_source_url"], 1)
        self.assertEqual(audit["no_timestamp"], 1)

    def test_audit_is_read_only(self):
        path = self.tmp.write_memory("professor_insights_cycle_001.json",
                                     document([good_insight()]))
        before = path.read_text(encoding="utf-8")
        provenance.audit(self.tmp.root, project=1)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_live_memory_is_uniform(self):
        """Замер по живым данным: память не различает проекты."""
        audit = provenance.audit(PROJECT_ROOT, project=1)
        self.assertEqual(audit["total"], 190)
        self.assertEqual(audit["clean"], 184)
        self.assertFalse(audit["applicable_projects"]["discriminates"])


class TestCliFreshnessAndProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = TempProject()

    def tearDown(self):
        self.tmp.cleanup()

    def test_report_check_exits_zero_when_fresh(self):
        self.tmp.write_memory("professor_insights_cycle_001.json", document([good_insight()]))
        self.tmp.write_report("MEMORY_REPORT.md", (
            "| файл | всего | мусор | дубли | чистых |\n"
            "|---|---|---|---|---|\n"
            "| professor_insights_cycle_001.json | 1 | 0 | 0 | 1 |\n"
            "| ИТОГО | 1 | 0 | 0 | 1 |\n"
        ))
        self.assertEqual(main(["--root", str(self.tmp.root), "report", "--check"]), 0)

    def test_report_check_exits_one_when_stale(self):
        self.tmp.write_memory("professor_insights_cycle_001.json", document([good_insight()]))
        self.tmp.write_report("MEMORY_REPORT.md", (
            "| файл | всего | мусор | дубли | чистых |\n"
            "|---|---|---|---|---|\n"
            "| professor_insights_cycle_001.json | 5 | 0 | 0 | 5 |\n"
            "| ИТОГО | 5 | 0 | 0 | 5 |\n"
        ))
        self.assertEqual(main(["--root", str(self.tmp.root), "report", "--check"]), 1)

    def test_provenance_json_runs(self):
        self.tmp.write_memory("professor_insights_cycle_001.json", document([good_insight()]))
        self.assertEqual(main(["--root", str(self.tmp.root), "provenance", "--json"]), 0)
        self.assertEqual(main(["--root", str(self.tmp.root), "provenance"]), 0)

    def test_live_report_check_passes(self):
        self.assertEqual(main(["--root", str(PROJECT_ROOT), "report", "--check"]), 0)


if __name__ == "__main__":
    unittest.main()