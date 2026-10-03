"""Тесты слоя памяти Project1 (p1_memory).

Запуск:  cd Project1 && python3 -m unittest discover -s tests -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory import chronicle, loader, validate  # noqa: E402
from p1_memory.chronicle import append_entry, has_entry, render_entry  # noqa: E402
from p1_memory.cli import main  # noqa: E402
from p1_memory.loader import MemoryError_, load, save_atomic, strip_markers  # noqa: E402
from p1_memory.validate import clean_insights, dedupe_key, is_junk, validate_document, validate_insight  # noqa: E402

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
    """Временный проект с файлами памяти."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="p1test-"))
        (self.root / "memory").mkdir()

    def write(self, name, data, marker=None):
        path = self.root / "memory" / name
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if marker:
            text = marker + "\n" + text
        path.write_text(text, encoding="utf-8")
        return path

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestStripMarkers(unittest.TestCase):
    def test_removes_hot_marker(self):
        clean, removed = strip_markers("# HOT\n{\"a\": 1}\n")
        self.assertEqual(removed, ["# HOT"])
        self.assertEqual(json.loads(clean), {"a": 1})

    def test_removes_cold_marker(self):
        clean, removed = strip_markers("# COLD\n{}\n")
        self.assertEqual(removed, ["# COLD"])
        self.assertEqual(json.loads(clean), {})

    def test_removes_several_markers(self):
        clean, removed = strip_markers("# HOT\n# COLD\n{}\n")
        self.assertEqual(removed, ["# HOT", "# COLD"])

    def test_keeps_content_when_no_marker(self):
        clean, removed = strip_markers('{"topic": "x"}\n')
        self.assertEqual(removed, [])
        self.assertEqual(clean, '{"topic": "x"}\n')

    def test_marker_inside_json_is_not_stripped(self):
        text = '{"topic": "# HOT"}\n'
        clean, removed = strip_markers(text)
        self.assertEqual(removed, [])
        self.assertEqual(json.loads(clean)["topic"], "# HOT")

    def test_empty_input(self):
        clean, removed = strip_markers("")
        self.assertEqual((clean, removed), ("", []))


class TestLoad(unittest.TestCase):
    def setUp(self):
        self.p = TempProject()

    def tearDown(self):
        self.p.cleanup()

    def test_loads_plain_file(self):
        path = self.p.write("professor_insights_cycle_001.json", document([good_insight()]))
        data = load(path)
        self.assertEqual(data["cycle"], 1)
        self.assertEqual(len(data["insights"]), 1)
        self.assertEqual(data["_markers_removed"], [])

    def test_loads_file_with_marker_injection(self):
        """Реальный дефект Project1: маркер `# HOT` ломал JSON."""
        path = self.p.write("professor_insights_cycle_002.json", document([good_insight()]), marker="# HOT")
        data = load(path)
        self.assertEqual(len(data["insights"]), 1)
        self.assertEqual(data["_markers_removed"], ["# HOT"])

    def test_missing_file_raises(self):
        with self.assertRaises(MemoryError_):
            load(self.p.root / "memory" / "нет-такого.json")

    def test_broken_json_raises(self):
        path = self.p.root / "memory" / "professor_insights_cycle_003.json"
        path.write_text("{не json", encoding="utf-8")
        with self.assertRaises(MemoryError_):
            load(path)

    def test_non_object_raises(self):
        path = self.p.root / "memory" / "professor_insights_cycle_004.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(MemoryError_):
            load(path)

    def test_missing_insights_key_raises(self):
        path = self.p.root / "memory" / "professor_insights_cycle_005.json"
        path.write_text('{"cycle": 1}', encoding="utf-8")
        with self.assertRaises(MemoryError_):
            load(path)

    def test_total_insights_is_defaulted(self):
        path = self.p.root / "memory" / "professor_insights_cycle_006.json"
        path.write_text(json.dumps({"cycle": 1, "insights": []}), encoding="utf-8")
        self.assertEqual(load(path)["total_insights"], 0)

    def test_real_project_files_load(self):
        """Штатная память проекта читается без исключений."""
        files = loader.iter_memory_files(PROJECT_ROOT)
        self.assertTrue(files, "в Project1 нет memory-файлов")
        for f in files:
            load(f)


class TestSaveAtomic(unittest.TestCase):
    def setUp(self):
        self.p = TempProject()

    def tearDown(self):
        self.p.cleanup()

    def test_writes_and_makes_backup(self):
        path = self.p.write("professor_insights_cycle_001.json", document([good_insight()]))
        save_atomic(path, document([good_insight()], total_insights=1))
        self.assertTrue((path.parent / (path.name + ".bak")).exists())
        self.assertEqual(len(load(path)["insights"]), 1)

    def test_no_tmp_litter(self):
        path = self.p.write("professor_insights_cycle_001.json", document([good_insight()]))
        save_atomic(path, document([]))
        self.assertEqual(list(self.p.root.glob("**/*.tmp")), [])

    def test_failure_keeps_known_good_file(self):
        """Искусственная ошибка записи не должна обнулить исходник."""

        class Unserializable:
            pass

        path = self.p.write("professor_insights_cycle_001.json", document([good_insight()]))
        broken = document([good_insight()])
        broken["insights"][0]["_bad"] = Unserializable()
        with self.assertRaises(TypeError):
            save_atomic(path, broken)
        self.assertEqual(len(load(path)["insights"]), 1)
        self.assertEqual(list(self.p.root.glob("**/*.tmp")), [])

    def test_internal_keys_not_persisted(self):
        path = self.p.write("professor_insights_cycle_001.json", document([]))
        save_atomic(path, load(path), backup=False)
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("_path", raw)
        self.assertNotIn("_markers_removed", raw)


class TestValidateInsight(unittest.TestCase):
    def test_good_record_has_no_problems(self):
        self.assertEqual(validate_insight(good_insight()), [])

    def test_missing_field(self):
        item = good_insight()
        del item["summary"]
        self.assertTrue(any("summary" in p for p in validate_insight(item)))

    def test_empty_topic(self):
        self.assertTrue(any("пустой topic" in p for p in validate_insight(good_insight(topic="  "))))

    def test_score_out_of_range(self):
        self.assertTrue(any("вне диапазона" in p for p in validate_insight(good_insight(relevance_score=1.5))))

    def test_score_wrong_type(self):
        problems = validate_insight(good_insight(relevance_score="0.9"))
        self.assertTrue(any("должен быть числом" in p for p in problems))

    def test_bool_is_not_a_number(self):
        problems = validate_insight(good_insight(relevance_score=True))
        self.assertTrue(any("должен быть числом" in p for p in problems))

    def test_wrong_list_type(self):
        problems = validate_insight(good_insight(tags="learned"))
        self.assertTrue(any("tags" in p for p in problems))

    def test_unknown_project(self):
        problems = validate_insight(good_insight(applicable_projects=[1, 9]))
        self.assertTrue(any("неизвестные" in p for p in problems))

    def test_non_string_tags(self):
        problems = validate_insight(good_insight(tags=[1, 2]))
        self.assertTrue(any("теги" in p for p in problems))

    def test_non_dict_item(self):
        self.assertTrue(validate_insight(["не словарь"]))


class TestValidateDocument(unittest.TestCase):
    def test_clean_document(self):
        doc = load_from(document([good_insight()]))
        self.assertEqual(validate_document(doc), [])

    def test_total_mismatch_detected(self):
        doc = load_from(document([good_insight()], total_insights=7))
        self.assertTrue(any("total_insights=7" in p for p in validate_document(doc)))

    def test_real_files_are_schema_clean(self):
        """Фактическая проверка штатной памяти Project1."""
        for f in loader.iter_memory_files(PROJECT_ROOT):
            self.assertEqual(validate_document(load(f)), [], f"{f}: проблемы схемы")

    def test_missing_header_field(self):
        doc = {"insights": [], "cycle": 1, "synced_at": "x"}
        self.assertTrue(any("project" in p for p in validate_document(load_from(doc))))


def load_from(doc):
    """Подготовка документа к validate_document (добавляет служебные ключи)."""
    return dict(doc, _path="<test>", _markers_removed=[])


class TestClean(unittest.TestCase):
    def test_unknown_topic_is_junk(self):
        self.assertTrue(is_junk(good_insight(topic="Unknown")))

    def test_empty_summary_is_junk(self):
        self.assertTrue(is_junk(good_insight(summary="   ")))

    def test_empty_topic_is_junk(self):
        self.assertTrue(is_junk(good_insight(topic="")))

    def test_non_dict_is_junk(self):
        self.assertTrue(is_junk(None))

    def test_good_record_is_not_junk(self):
        self.assertFalse(is_junk(good_insight()))

    def test_dedupe_key_is_casefolded(self):
        self.assertEqual(dedupe_key(good_insight(topic="AbC")), ("abc", "https://example.org/a.md"))

    def test_clean_removes_junk_and_duplicates(self):
        items = [good_insight(), good_insight(), good_insight(topic="Unknown"), good_insight(topic="Другая")]
        kept, stats = clean_insights(items)
        self.assertEqual(stats, {"input": 4, "junk": 1, "duplicates": 1, "kept": 2})

    def test_clean_keeps_distinct_sources(self):
        a = good_insight(source_url="https://example.org/a.md")
        b = good_insight(source_url="https://example.org/b.md")
        kept, stats = clean_insights([a, b])
        self.assertEqual(stats["kept"], 2)

    def test_real_data_has_six_junk_and_no_dupes(self):
        """Факт, зафиксированный на штатной памяти Project1 (2 файла, 190 записей)."""
        junk = dupes = raw = 0
        for f in loader.iter_memory_files(PROJECT_ROOT):
            _, stats = clean_insights(load(f)["insights"])
            junk += stats["junk"]
            dupes += stats["duplicates"]
            raw += stats["input"]
        self.assertEqual((raw, junk, dupes), (190, 6, 0))


class TestCli(unittest.TestCase):
    def setUp(self):
        self.p = TempProject()
        self.p.write("professor_insights_cycle_001.json",
                     document([good_insight(), good_insight(topic="Unknown")]), marker="# HOT")
        self.argv = ["p1_memory", "--root", str(self.p.root)]

    def tearDown(self):
        self.p.cleanup()

    def test_report_exit_zero(self):
        self.assertEqual(main(self.argv + ["report"]), 0)

    def test_report_json_is_valid(self):
        out = _capture(self.argv + ["report", "--json"])
        data = json.loads(out)
        self.assertEqual(data["totals"]["files"], 1)
        self.assertEqual(data["totals"]["junk"], 1)

    def test_validate_exit_zero_on_clean(self):
        self.p.write("professor_insights_cycle_002.json", document([good_insight()]))
        self.assertEqual(main(self.argv + ["validate"]), 0)

    def test_validate_exit_one_on_broken(self):
        self.p.write("professor_insights_cycle_002.json", document([good_insight()], total_insights=99))
        self.assertEqual(main(self.argv + ["validate"]), 1)

    def test_dedupe_dry_run_writes_nothing(self):
        before = (self.p.root / "memory" / "professor_insights_cycle_001.json").read_text(encoding="utf-8")
        self.assertEqual(main(self.argv + ["dedupe"]), 0)
        after = (self.p.root / "memory" / "professor_insights_cycle_001.json").read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_dedupe_fix_applies(self):
        self.assertEqual(main(self.argv + ["dedupe", "--fix"]), 0)
        path = self.p.root / "memory" / "professor_insights_cycle_001.json"
        self.assertEqual(len(load(path)["insights"]), 1)
        self.assertTrue((path.parent / (path.name + ".bak")).exists())

    def test_missing_memory_returns_error(self):
        empty = TempProject()
        try:
            self.assertEqual(main(["p1_memory", "--root", str(empty.root), "report"]), 1)
        finally:
            empty.cleanup()

    def test_real_project_report_runs(self):
        self.assertEqual(main(["p1_memory", "--root", str(PROJECT_ROOT), "report"]), 0)


class TestChronicle(unittest.TestCase):
    """Атомарный аппенд в CHRONICLE.md."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="p1chron-"))
        self.path = self.dir / "CHRONICLE.md"
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_render_has_stamp_title_and_separator(self):
        entry = render_entry("Слот 7", "сделано A\nсделано B", "2026-10-03 03:00:00")
        self.assertEqual(
            entry,
            "### 2026-10-03 03:00:00 — Слот 7\nсделано A\nсделано B\n\n---\n\n",
        )

    def test_append_creates_file_when_absent(self):
        append_entry(self.path, "Первый слот", "тело", "2026-10-03 03:00:00")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("### 2026-10-03 03:00:00 — Первый слот", text)
        self.assertTrue(text.endswith("---\n\n"))

    def test_append_keeps_previous_history_intact(self):
        self.path.write_text("# Журнал\n\nстарые записи\n", encoding="utf-8")
        append_entry(self.path, "Слот 8", "новое", "2026-10-03 03:10:00")
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Журнал\n\nстарые записи\n"))
        self.assertIn("Слот 8", text)

    def test_append_repairs_missing_final_newline(self):
        self.path.write_text("# Журнал\n\nхвост без перевода", encoding="utf-8")
        append_entry(self.path, "Слот 9", "новое", "2026-10-03 03:20:00")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("хвост без перевода\n### 2026-10-03 03:20:00 — Слот 9", text)

    def test_repeat_title_is_noop(self):
        append_entry(self.path, "Слот 10", "тело", "2026-10-03 03:30:00")
        size = self.path.stat().st_size
        append_entry(self.path, "Слот 10", "тело", "2026-10-03 03:45:00")
        self.assertEqual(self.path.stat().st_size, size)
        self.assertEqual(self.path.read_text(encoding="utf-8").count("Слот 10"), 1)

    def test_backup_is_created(self):
        self.path.write_text("# Журнал\n", encoding="utf-8")
        append_entry(self.path, "Слот 11", "тело", "2026-10-03 03:40:00")
        self.assertTrue((self.dir / "CHRONICLE.md.bak").exists())

    def test_empty_title_rejected(self):
        with self.assertRaises(ValueError):
            append_entry(self.path, "   ", "тело", "2026-10-03 03:50:00")

    def test_has_entry_does_not_match_partial(self):
        self.assertFalse(has_entry("### 2026-10-03 — Слот 1", "Слот"))


class TestChronicleCli(unittest.TestCase):
    """Команда chronicle через CLI."""

    def setUp(self):
        self.tmp = TempProject()
        self.tmp.write("professor_insights_cycle_001.json", document([good_insight()]))
        self.addCleanup(self.tmp.cleanup)
        self.argv = ["p1_memory", "--root", str(self.tmp.root)]

    def test_chronicle_writes_entry(self):
        code = main(self.argv + ["chronicle", "--title", "Слот 1", "--body", "сделано",
                                 "--stamp", "2026-10-03 04:00:00"])
        self.assertEqual(code, 0)
        text = (self.tmp.root / "CHRONICLE.md").read_text(encoding="utf-8")
        self.assertIn("### 2026-10-03 04:00:00 — Слот 1", text)

    def test_chronicle_is_idempotent(self):
        self.argv += ["chronicle", "--title", "Слот 1", "--body", "сделано", "--stamp", "2026-10-03 04:00:00"]
        main(self.argv)
        size = (self.tmp.root / "CHRONICLE.md").stat().st_size
        main(self.argv)
        self.assertEqual((self.tmp.root / "CHRONICLE.md").stat().st_size, size)

    def test_chronicle_stats_appends_summary(self):
        main(self.argv + ["chronicle", "--title", "Слот 2", "--stamp", "2026-10-03 04:10:00", "--stats"])
        text = (self.tmp.root / "CHRONICLE.md").read_text(encoding="utf-8")
        self.assertIn("- инсайтов: 1", text)
        self.assertIn("- чистых: 1", text)

    def test_chronicle_does_not_touch_memory(self):
        path = self.tmp.root / "memory" / "professor_insights_cycle_001.json"
        before = path.read_text(encoding="utf-8")
        main(self.argv + ["chronicle", "--title", "Слот 3", "--stamp", "2026-10-03 04:20:00"])
        self.assertEqual(path.read_text(encoding="utf-8"), before)


def _capture(argv):
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


if __name__ == "__main__":
    unittest.main()