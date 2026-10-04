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
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory import chronicle, crossfile, loader, validate  # noqa: E402
from p1_memory.chronicle import append_entry, has_entry, render_entry  # noqa: E402
from p1_memory.cli import main  # noqa: E402
from p1_memory.crossfile import count_crossfile, merged_view, plan_crossfile  # noqa: E402
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


class DoctorTests(unittest.TestCase):
    """Целостность исходников: класс дефекта, найденный в слоте 2026-10-03 11:01.

    Регрессия живой порчи: `chronicle.py` лежал на диске с NUL-байтом в
    docstring, обрывом текста и строкой «п.Threading is disabled for this
    response.». Пакет целиком не импортировался.
    """

    def setUp(self):
        from p1_memory import doctor
        self.doctor = doctor
        self.tmp = tempfile.TemporaryDirectory(prefix="p1doctor-")
        self.root = Path(self.tmp.name)
        (self.root / "p1_memory").mkdir()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, name: str, text: str = "", raw: Optional[bytes] = None):
        target = self.root / "p1_memory" / name
        if raw is not None:
            target.write_bytes(raw)
        else:
            target.write_text(text, encoding="utf-8")
        return target

    def _kinds(self, path):
        return {f.kind for f in self.doctor.scan_file(path)}

    # --- регрессия на живой порче ---------------------------------------

    def test_detects_null_byte_in_source(self):
        """Живой дефект: NUL-байт роняет импорт всего пакета."""
        path = self._write("broken.py", raw=b'"""Doc."""\n\nVALUE = 1\n\x00\ndef f():\n    return 2\n')
        self.assertIn("null-байты", self._kinds(path))
        self.assertTrue(self.doctor.is_blocking(self.doctor.scan_file(path)))

    def test_detects_junk_line_from_stream_tail(self):
        """Живой дефект: служебный хвост конвейера внутри docstring."""
        path = self._write(
            "broken.py",
            '"""Начало.\n\nп.Threading is disabled for this response.\n\nVALUE = 1\n',
        )
        self.assertIn("служебный-мусор", self._kinds(path))

    def test_truncated_file_reported(self):
        """Обрыв записи: незакрытая скобка ловится правилом «синтаксис»."""
        path = self._write("broken.py", "def f():\n    return {\n")
        self.assertIn("синтаксис", self._kinds(path))
        self.assertTrue(self.doctor.is_blocking(self.doctor.scan_file(path)))

    # --- границы правил: ложных срабатываний быть не должно -------------

    def test_clean_file_has_no_findings(self):
        path = self._write("ok.py", "VALUE = 1\n\ndef f():\n    return VALUE\n")
        self.assertEqual(self.doctor.scan_file(path), [])

    def test_mention_of_junk_phrase_is_not_corruption(self):
        """Упоминание служебной фразы в обычном тексте — не порча.

        Регрессия на границу правила: первая версия доктора ловила само себя,
        потому что фраза встречалась в его же docstring.
        """
        text = (
            "def f():\n"
            '    return "Threading is disabled for this response."\n'
            "# а это в комментарии: Threading is disabled for this response\n"
            "X = 1\n"
        )
        path = self._write("ok.py", text)
        self.assertEqual(self.doctor.scan_file(path), [])

    def test_truncation_is_warning_not_blocking(self):
        """Нет завершающего \\n — подсказка, а не порча.

        Инструмент записи в этой среде срезает последний перевод строки у
        всех файлов; блокирующим такое делало бы doctor бесполезным.
        """
        path = self._write("ok.py", "X = 1")
        findings = self.doctor.scan_file(path)
        self.assertEqual([f.kind for f in findings], ["обрыв"])
        self.assertFalse(self.doctor.is_blocking(findings))

    def test_invalid_utf8_detected(self):
        path = self._write("broken.py", raw=b"X = 1\n\xff\xfe\n")
        self.assertIn("не-utf8", self._kinds(path))

    # --- API --------------------------------------------------------------

    def test_scan_tree_clean_project(self):
        self._write("a.py", "A = 1\n")
        self._write("b.py", "B = 2\n")
        self.assertEqual(self.doctor.scan_tree(self.root), [])

    def test_scan_tree_finds_corrupt_file(self):
        self._write("good.py", "A = 1\n")
        self._write("bad.py", raw=b"A = 1\n\x00")
        findings = self.doctor.scan_tree(self.root)
        self.assertTrue(self.doctor.is_blocking(findings))
        self.assertIn("bad.py", {f.path for f in findings})

    def test_compile_check_catches_syntax_error(self):
        (self.root / "p1_memory" / "broken.py").write_text("def f(:\n", encoding="utf-8")
        findings = self.doctor.compile_check(self.root)
        self.assertTrue(findings)
        self.assertEqual(findings[0].kind, "не компилируется")

    def test_summarize_counts_by_kind(self):
        self._write("a.py", raw=b"A = 1\n\x00")
        self._write("b.py", "B = 2")
        counts = self.doctor.summarize(self.doctor.scan_tree(self.root))
        self.assertEqual(counts.get("null-байты"), 1)
        self.assertGreaterEqual(counts.get("обрыв", 0), 1)

    def test_empty_directory_has_no_findings(self):
        self.assertEqual(self.doctor.scan_tree(self.root), [])


class DoctorCliTests(unittest.TestCase):
    """Команда `doctor`: exit-коды и формат вывода."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p1doctorcli-")
        self.root = Path(self.tmp.name)
        (self.root / "p1_memory").mkdir()
        self.addCleanup(self.tmp.cleanup)
        self.root_argv = ["--root", str(self.root)]

    def _run(self, extra=None):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(self.root_argv + ["doctor"] + (extra or []))
        return code, buf.getvalue()

    def test_doctor_exit_zero_on_clean_tree(self):
        (self.root / "p1_memory" / "ok.py").write_text("X = 1\n", encoding="utf-8")
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn("порчи нет", out)

    def test_doctor_exit_one_on_null_byte(self):
        (self.root / "p1_memory" / "bad.py").write_bytes(b"X = 1\n\x00")
        code, out = self._run()
        self.assertEqual(code, 1)
        self.assertIn("ПОРЧА", out)
        self.assertIn("null-байты", out)

    def test_doctor_json_is_valid(self):
        (self.root / "p1_memory" / "bad.py").write_bytes(b"X = 1\n\x00")
        code, out = self._run(["--json"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertTrue(data["blocking"])
        self.assertEqual(data["summary"].get("null-байты"), 1)

    def test_doctor_hides_warnings_by_default(self):
        """Предупреждения не должны тонуть в выводе блокирующих находок."""
        (self.root / "p1_memory" / "ok.py").write_text("X = 1", encoding="utf-8")
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertNotIn("[ПОРЧА]", out)
        self.assertIn("предупреждений без блокирующей силы", out)

    def test_doctor_all_shows_warnings_without_porcha_mark(self):
        """С --all предупреждения видны, но не помечены как порча."""
        (self.root / "p1_memory" / "ok.py").write_text("X = 1", encoding="utf-8")
        code, out = self._run(["--all"])
        self.assertEqual(code, 0)
        self.assertIn("обрыв", out)
        self.assertNotIn("[ПОРЧА]", out)


class CrossFileTests(unittest.TestCase):
    """Кросс-файловая дедупликация.

    Правило выбора победителя: более поздний `timestamp` записи, при равенстве —
    более ранний `synced_at` файла, затем имя файла, затем позиция.
    """

    def setUp(self):
        self.tmp = TempProject()
        self.addCleanup(self.tmp.cleanup)

    def _pair(self):
        """Два файла: старый цикл и новый, тема одна и та же."""
        old_url = "https://example.org/one.md"
        old = self.tmp.write(
            "professor_insights_cycle_001.json",
            document([good_insight(topic="Тема один", source_url=old_url)], synced_at="2026-08-16T08:10:33+00:00"),
        )
        new = self.tmp.write(
            "professor_insights_cycle_777.json",
            document(
                [good_insight(topic="Тема один", source_url=old_url, summary="Поздняя копия")],
                cycle=777,
                synced_at="2026-10-01T12:00:00+00:00",
            ),
        )
        docs = [load(old), load(new)]
        return [(old, docs[0]), (new, docs[1])]

    def test_earlier_synced_at_wins(self):
        plan, stats = plan_crossfile(self._pair())
        self.assertEqual(stats["cross_file_duplicates"], 1)
        by_path = {e["path"]: e for e in plan}
        self.assertEqual(len(by_path[plan[0]["path"]]["kept"]), 1)
        # файл с поздним synced_at должен остаться пустым
        late = [e for e in plan if "777" in e["path"].name][0]
        self.assertEqual(late["kept"], [])

    def test_kept_record_comes_from_older_file(self):
        plan, _ = plan_crossfile(self._pair())
        kept = merged_view(self._pair())[0]
        self.assertEqual(kept["summary"], "Краткое изложение темы")

    def test_tie_broken_by_filename(self):
        """Одинаковый synced_at — побеждает файл с меньшим именем."""
        url = "https://example.org/tie.md"
        a = self.tmp.write("professor_insights_cycle_001.json", document([good_insight(source_url=url)]))
        b = self.tmp.write(
            "professor_insights_cycle_002.json",
            document([good_insight(source_url=url, summary="Вторая копия")], cycle=2),
        )
        docs = [load(a), load(b)]
        plan, stats = plan_crossfile([(a, docs[0]), (b, docs[1])])
        self.assertEqual(stats["cross_file_duplicates"], 1)
        first = [e for e in plan if "cycle_001" in e["path"].name][0]
        self.assertEqual(len(first["kept"]), 1)

    def test_disjoint_topics_are_untouched(self):
        a = self.tmp.write("professor_insights_cycle_001.json", document([good_insight(source_url="https://example.org/a.md")]))
        b = self.tmp.write(
            "professor_insights_cycle_002.json",
            document([good_insight(topic="Другая", source_url="https://example.org/b.md")], cycle=2),
        )
        docs = [load(a), load(b)]
        plan, stats = plan_crossfile([(a, docs[0]), (b, docs[1])])
        self.assertEqual(stats["cross_file_duplicates"], 0)
        self.assertEqual(sum(len(e["kept"]) for e in plan), 2)

    def test_count_crossfile_matches_plan(self):
        pairs = self._pair()
        self.assertEqual(count_crossfile(pairs), plan_crossfile(pairs)[1]["cross_file_duplicates"])

    def test_junk_is_dropped_before_crossfile_pass(self):
        """Мусорная запись не должна блокировать валидную более позднюю."""
        url = "https://example.org/j.md"
        a = self.tmp.write(
            "professor_insights_cycle_001.json",
            document([good_insight(source_url=url), good_insight(topic="Unknown", source_url="")], synced_at="2026-08-16T08:10:33+00:00"),
        )
        b = self.tmp.write(
            "professor_insights_cycle_002.json",
            document([good_insight(source_url=url, summary="Хорошая копия")], cycle=2, synced_at="2026-10-01T12:00:00+00:00"),
        )
        docs = [load(a), load(b)]
        _, stats = plan_crossfile([(a, docs[0]), (b, docs[1])])
        self.assertEqual(stats["junk"], 1)
        self.assertEqual(stats["cross_file_duplicates"], 1)

    def test_empty_source_url_not_merged(self):
        """Две безымянные мысли — не дубль (нет доказательства тождества)."""
        a = self.tmp.write("professor_insights_cycle_001.json", document([good_insight(source_url="")]))
        b = self.tmp.write(
            "professor_insights_cycle_002.json",
            document([good_insight(source_url="", summary="Другая мысль без ссылки")], cycle=2),
        )
        docs = [load(a), load(b)]
        _, stats = plan_crossfile([(a, docs[0]), (b, docs[1])])
        self.assertEqual(stats["cross_file_duplicates"], 0)

    def test_merged_view_is_deterministic(self):
        pairs = self._pair()
        first = merged_view(pairs)
        second = merged_view(list(reversed(pairs)))
        self.assertEqual(first, second)

    def test_fresher_record_wins_over_earlier_file(self):
        """Поздний timestamp записи побеждает даже у файла с ранним synced_at.

        Замер `tests/probe_winner.py`: номер цикла в имени файла не дата
        (cycle_1351 записан раньше cycle_001), поэтому правило «побеждает ранний
        файл» закрепляло устаревшее содержимое.
        """
        url = "https://example.org/fresh.md"
        a = self.tmp.write(
            "professor_insights_cycle_1351.json",
            document([good_insight(source_url=url, summary="Устаревшая копия",
                                   timestamp="2026-08-14T00:00:00+00:00")],
                     cycle=1351, synced_at="2026-08-14T00:00:00+00:00"),
        )
        b = self.tmp.write(
            "professor_insights_cycle_001.json",
            document([good_insight(source_url=url, summary="Свежая копия",
                                   timestamp="2026-08-16T08:10:33+00:00")],
                     synced_at="2026-08-16T08:10:33+00:00"),
        )
        docs = [load(a), load(b)]
        pairs = [(a, docs[0]), (b, docs[1])]
        plan, stats = plan_crossfile(pairs)
        self.assertEqual(stats["cross_file_duplicates"], 1)
        late = [e for e in plan if "1351" in e["path"].name][0]
        self.assertEqual(late["kept"], [])
        self.assertEqual(merged_view(pairs)[0]["summary"], "Свежая копия")

    def test_missing_timestamp_loses_to_stamped_record(self):
        """Запись без timestamp не ломает ранжирование: она проигрывает помеченной."""
        url = "https://example.org/nots.md"
        without_stamp = good_insight(source_url=url)
        without_stamp.pop("timestamp")
        a = self.tmp.write(
            "professor_insights_cycle_001.json",
            document([without_stamp], synced_at="2026-08-14T00:00:00+00:00"),
        )
        b = self.tmp.write(
            "professor_insights_cycle_002.json",
            document([good_insight(source_url=url, summary="Вторая")], cycle=2,
                     synced_at="2026-08-16T08:10:33+00:00"),
        )
        docs = [load(a), load(b)]
        pairs = [(a, docs[0]), (b, docs[1])]
        plan, stats = plan_crossfile(pairs)
        self.assertEqual(stats["cross_file_duplicates"], 1)
        self.assertEqual([e for e in plan if "cycle_001" in e["path"].name][0]["kept"], [])
        self.assertEqual(len([e for e in plan if "cycle_002" in e["path"].name][0]["kept"]), 1)


class CrossFileCliTests(unittest.TestCase):
    """`dedupe --scope all` через CLI: dry-run, --fix, идемпотентность."""

    def setUp(self):
        self.tmp = TempProject()
        self.addCleanup(self.tmp.cleanup)
        url = "https://example.org/dup.md"
        self.tmp.write(
            "professor_insights_cycle_001.json",
            document([good_insight(source_url=url), good_insight(topic="Только тут", source_url="https://example.org/only.md")],
                     synced_at="2026-08-16T08:10:33+00:00"),
        )
        self.tmp.write(
            "professor_insights_cycle_002.json",
            document([good_insight(source_url=url, summary="Повтор")], cycle=2, synced_at="2026-10-01T12:00:00+00:00"),
        )
        self.argv = ["p1_memory", "--root", str(self.tmp.root)]

    def _run(self, extra):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(self.argv + ["dedupe"] + extra)
        return code, buf.getvalue()

    def test_dry_run_does_not_write(self):
        before = (self.tmp.root / "memory" / "professor_insights_cycle_002.json").read_text(encoding="utf-8")
        code, out = self._run(["--scope", "all"])
        self.assertEqual(code, 0)
        after = (self.tmp.root / "memory" / "professor_insights_cycle_002.json").read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertIn("1", out)

    def test_json_reports_scope_and_totals(self):
        code, out = self._run(["--scope", "all", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["scope"], "all")
        self.assertTrue(data["dry_run"])
        self.assertEqual(data["totals"]["cross_file_duplicates"], 1)
        self.assertEqual(data["totals"]["kept"], 2)

    def test_fix_removes_duplicate_and_makes_backup(self):
        code, out = self._run(["--scope", "all", "--fix"])
        self.assertEqual(code, 0)
        doc = load(self.tmp.root / "memory" / "professor_insights_cycle_002.json")
        self.assertEqual(doc["insights"], [])
        self.assertTrue((self.tmp.root / "memory" / "professor_insights_cycle_002.json.bak").exists())
        self.assertIn("1", out)

    def test_second_run_is_idempotent(self):
        self._run(["--scope", "all", "--fix"])
        code, out = self._run(["--scope", "all", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["totals"]["cross_file_duplicates"], 0)
        self.assertEqual(data["totals"]["kept"], 2)

    def test_fix_preserves_oldest_content(self):
        self._run(["--scope", "all", "--fix"])
        doc = load(self.tmp.root / "memory" / "professor_insights_cycle_001.json")
        self.assertEqual(len(doc["insights"]), 2)
        self.assertEqual(doc["insights"][0]["summary"], "Краткое изложение темы")

    def test_default_scope_still_works_filewise(self):
        """Старое поведение `dedupe` без --scope не должно сломаться."""
        code, out = self._run(["--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["scope"], "file")
        self.assertEqual(data["totals"]["cross_file_duplicates"], 0)
        self.assertEqual(data["totals"]["kept"], 3)


class RealDataCrossFileTests(unittest.TestCase):
    """Реальные файлы Project1: измеренный дефект кросс-файловых дублей.

    Числа зафиксированы харнессом `tests/harness_crossfile.py` (2026-10-03):
    190 записей, 100 уникальных пар `(topic, source_url)`, из них 84 пары
    встречаются сразу в двух файлах. Тест — регресс: если данные памяти
    обновятся новым циклом Профессора, числа изменятся, и это нужно увидеть
    осознанно (пересчитать харнессом), а не молча получить зелёный прогон.
    """

    def test_measured_duplicate_count(self):
        pairs = list(crossfile_pairs(PROJECT_ROOT))
        plan, stats = plan_crossfile(pairs)
        self.assertEqual(stats["files"], len(pairs))
        self.assertGreater(stats["cross_file_duplicates"], 0)
        self.assertLess(
            stats["cross_file_duplicates"],
            stats["input"],
            "реальные данные обязаны содержать и уникальные записи",
        )
        # после глобальной очистки ключи не должны повторяться между файлами
        keys = [dedupe_key(i) for i in merged_view(pairs)]
        self.assertEqual(len(keys), len(set(keys)))

    def test_harness_numbers_hold(self):
        """Регресс на числа харнесса: 190 входных, 84 кросс-файловых, 100 kept."""
        pairs = list(crossfile_pairs(PROJECT_ROOT))
        _, stats = plan_crossfile(pairs)
        self.assertEqual(stats["input"], 190, stats)
        self.assertEqual(stats["cross_file_duplicates"], 84, stats)
        self.assertEqual(stats["kept"], 100, stats)

    def test_real_run_of_harness_reports_same(self):
        """Тот же замер реальным запуском харнесса, а не импортом модуля."""
        import subprocess
        script = PROJECT_ROOT / "tests" / "harness_crossfile.py"
        proc = subprocess.run([sys.executable, str(script)],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        report = json.loads(proc.stdout[proc.stdout.index("{"):proc.stdout.rindex("}") + 1])
        self.assertEqual(report["records"], 190)
        self.assertEqual(report["unique_pairs"], 100)
        self.assertEqual(report["cross_file_pairs"], 84)


def crossfile_pairs(root):
    """Список (путь, документ) по файлам памяти проекта."""
    return [(path, load(path)) for path in loader.iter_memory_files(root)]


if __name__ == "__main__":
    unittest.main()