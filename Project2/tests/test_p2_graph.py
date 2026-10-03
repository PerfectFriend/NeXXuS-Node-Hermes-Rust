"""Тесты слоя памяти и графа Project2 (p2_graph).

Прогон: python3 -m unittest discover -s tests -v  (из корня Project2)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from p2_graph import EDGE_TYPES  # noqa: E402
from p2_graph.cli import EXIT_DATA, EXIT_OK, EXIT_USAGE, main  # noqa: E402
from p2_graph.graph import (  # noqa: E402
    build_graph,
    centrality,
    edge_type_counts,
    metrics,
    node_id,
    query as graph_query,
    tokens_of,
)
from p2_graph.loader import (  # noqa: E402
    MemoryError_,
    atomic_write,
    iter_insights,
    load,
    load_all,
    strip_markers,
)
from p2_graph.validate import (  # noqa: E402
    clean_insights,
    find_duplicates,
    is_junk,
    validate_file,
    validate_insight,
)

REAL_MEMORY = ROOT / "memory"


def make_insight(**kw):
    topic = kw.get("topic", "Topic")
    base = {
        "topic": topic,
        "category": "Textbook",
        # Сводка привязана к теме: одинаковый служебный текст у всех фикстур
        # создавал бы ложное ребро token_overlap у любой пары записей.
        "summary": f"сводка {topic}",
        "source_url": "note.md",
        "source_type": "Textbook",
        "relevance_score": 0.7,
        "applicable_projects": [2],
        "tags": ["learned"],
        "timestamp": "2026-08-16T08:10:33+00:00",
    }
    base.update(kw)
    return base


def write_memory(directory, name: str, cycle: int, insights, marker=None, project=2) -> Path:
    data = {"cycle": cycle, "project": project, "synced_at": "2026-08-16T08:10:33+00:00",
            "total_insights": len(insights), "insights": insights}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if marker:
        text = marker + "\n" + text
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


# ---------------------------------------------------------------- загрузка

class TestStripMarkers(unittest.TestCase):
    def test_removes_hot(self):
        clean, removed = strip_markers("# HOT\n{\"a\":1}")
        self.assertEqual(removed, ["# HOT"])
        self.assertEqual(clean, '{"a":1}')

    def test_removes_both_markers_in_order(self):
        clean, removed = strip_markers("# HOT\n# COLD\n{}\n")
        self.assertEqual(removed, ["# HOT", "# COLD"])
        self.assertEqual(clean, "{}\n")

    def test_keeps_normal_text(self):
        clean, removed = strip_markers("# HOTCODE\n{}\n")
        self.assertEqual(removed, [])
        self.assertEqual(clean, "# HOTCODE\n{}\n")

    def test_marker_inside_body_is_kept(self):
        clean, _ = strip_markers('{"x": "# HOT"}')
        self.assertEqual(clean, '{"x": "# HOT"}')


class TestLoad(TempDirCase):
    def test_load_with_marker_returns_data(self):
        path = write_memory(self.dir, "professor_insights_cycle_007.json", 7,
                            [make_insight()], marker="# HOT")
        data = load(path)
        self.assertEqual(len(data["insights"]), 1)
        self.assertEqual(data["_markers_removed"], ["# HOT"])

    def test_load_without_marker(self):
        path = write_memory(self.dir, "professor_insights_cycle_001.json", 1, [make_insight()])
        self.assertEqual(load(path)["_markers_removed"], [])

    def test_missing_file_raises(self):
        with self.assertRaises(MemoryError_):
            load(self.dir / "nope.json")

    def test_broken_json_raises(self):
        path = self.dir / "professor_insights_cycle_002.json"
        path.write_text("{не json", encoding="utf-8")
        with self.assertRaises(MemoryError_):
            load(path)

    def test_not_object_raises(self):
        path = self.dir / "professor_insights_cycle_003.json"
        path.write_text("[1,2]", encoding="utf-8")
        with self.assertRaises(MemoryError_):
            load(path)

    def test_missing_insights_raises(self):
        path = self.dir / "professor_insights_cycle_004.json"
        path.write_text('{"cycle": 4}', encoding="utf-8")
        with self.assertRaises(MemoryError_):
            load(path)

    def test_total_insights_defaulted(self):
        path = self.dir / "professor_insights_cycle_005.json"
        path.write_text('{"cycle": 5, "insights": [{}]}', encoding="utf-8")
        self.assertEqual(load(path)["total_insights"], 1)

    def test_load_all_sorted_by_cycle(self):
        write_memory(self.dir, "professor_insights_cycle_1351.json", 1351, [make_insight()])
        write_memory(self.dir, "professor_insights_cycle_001.json", 1, [make_insight()])
        files = load_all(self.dir)
        self.assertEqual([f["_cycle"] for f in files], [1, 1351])

    def test_load_all_missing_dir(self):
        with self.assertRaises(MemoryError_):
            load_all(self.dir / "нет")

    def test_iter_insights_adds_service_fields(self):
        path = write_memory(self.dir, "professor_insights_cycle_009.json", 9,
                            [make_insight(), make_insight(topic="Другая")])
        rows = list(iter_insights(load_all(self.dir)))
        self.assertEqual([r["_index"] for r in rows], [0, 1])
        self.assertEqual(rows[0]["_file"], "professor_insights_cycle_009.json")
        self.assertEqual(rows[0]["_cycle"], 9)

    def test_iter_insights_skips_non_dict(self):
        path = self.dir / "professor_insights_cycle_010.json"
        path.write_text('{"cycle":10,"insights":["строка",{"topic":"T"}]}', encoding="utf-8")
        rows = list(iter_insights(load_all(self.dir)))
        self.assertEqual(len(rows), 1)

    def test_real_project2_memory_loads(self):
        files = load_all(REAL_MEMORY)
        self.assertEqual(len(files), 2)
        self.assertEqual(sum(len(f["insights"]) for f in files), 190)


# -------------------------------------------------------------- атомарность

class TestAtomicWrite(TempDirCase):
    def test_creates_backup(self):
        path = write_memory(self.dir, "professor_insights_cycle_001.json", 1, [make_insight()])
        data = load(path)
        data["insights"] = []
        data["total_insights"] = 0
        backup = atomic_write(path, data)
        self.assertTrue(Path(backup).exists())
        self.assertEqual(len(load(backup)["insights"]), 1)

    def test_no_tmp_litter(self):
        path = write_memory(self.dir, "professor_insights_cycle_001.json", 1, [make_insight()])
        data = load(path)
        atomic_write(path, data)
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])

    def test_known_good_survives_failed_serialisation(self):
        path = write_memory(self.dir, "professor_insights_cycle_001.json", 1, [make_insight()])
        before = path.read_text(encoding="utf-8")
        with self.assertRaises(TypeError):
            atomic_write(path, {"insights": [object()]})
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])

    def test_written_file_is_valid_json(self):
        path = self.dir / "professor_insights_cycle_002.json"
        atomic_write(path, {"insights": [make_insight(topic="Кириллица")]}, backup=False)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["insights"][0]["topic"],
                         "Кириллица")

    def test_unicode_not_escaped(self):
        path = self.dir / "professor_insights_cycle_003.json"
        atomic_write(path, {"insights": [make_insight(topic="тест")]}, backup=False)
        self.assertIn("тест", path.read_text(encoding="utf-8"))


# -------------------------------------------------------------- валидация

class TestValidateInsight(unittest.TestCase):
    def test_valid_has_no_problems(self):
        self.assertEqual(validate_insight(make_insight()), [])

    def test_missing_field(self):
        item = make_insight()
        del item["topic"]
        self.assertTrue(any("topic" in p for p in validate_insight(item)))

    def test_not_dict(self):
        self.assertTrue(validate_insight("строка"))

    def test_wrong_type_str_field(self):
        self.assertTrue(validate_insight(make_insight(topic=5)))

    def test_wrong_type_list_field(self):
        self.assertTrue(validate_insight(make_insight(tags="learned")))

    def test_relevance_out_of_range_high(self):
        self.assertTrue(validate_insight(make_insight(relevance_score=1.5)))

    def test_relevance_out_of_range_low(self):
        self.assertTrue(validate_insight(make_insight(relevance_score=-0.1)))

    def test_relevance_bool_rejected(self):
        self.assertTrue(validate_insight(make_insight(relevance_score=True)))

    def test_relevance_not_number(self):
        self.assertTrue(validate_insight(make_insight(relevance_score="0.7")))

    def test_empty_topic(self):
        self.assertTrue(validate_insight(make_insight(topic="   ")))

    def test_bad_project_id(self):
        self.assertTrue(validate_insight(make_insight(applicable_projects=[9])))

    def test_where_label_present(self):
        item = make_insight(topic=5)
        self.assertTrue(validate_insight(item, where="f.json[3]")[0].startswith("f.json[3]"))


class TestValidateFile(TempDirCase):
    def test_consistent_file_ok(self):
        path = write_memory(self.dir, "professor_insights_cycle_001.json", 1, [make_insight()])
        self.assertEqual(validate_file(load(path)), [])

    def test_total_insights_mismatch(self):
        path = self.dir / "professor_insights_cycle_001.json"
        path.write_text(json.dumps({"total_insights": 5, "insights": [make_insight()]}),
                        encoding="utf-8")
        problems = validate_file(load(path))
        self.assertTrue(any("total_insights" in p for p in problems))

    def test_real_project2_memory_is_schema_valid(self):
        problems = []
        for f in load_all(REAL_MEMORY):
            problems.extend(validate_file(f))
        self.assertEqual(problems, [])


class TestJunkAndDuplicates(unittest.TestCase):
    def test_unknown_topic_is_junk(self):
        junk, reason = is_junk(make_insight(topic="Unknown"))
        self.assertTrue(junk)
        self.assertIn("Unknown", reason)

    def test_empty_summary_is_junk(self):
        self.assertTrue(is_junk(make_insight(summary="  "))[0])

    def test_empty_topic_is_junk(self):
        self.assertTrue(is_junk(make_insight(topic=""))[0])

    def test_good_insight_not_junk(self):
        self.assertFalse(is_junk(make_insight())[0])

    def test_non_dict_is_junk(self):
        self.assertTrue(is_junk("строка")[0])

    def test_find_duplicates(self):
        rows = [make_insight(), make_insight(), make_insight(topic="Другая")]
        dups = find_duplicates(rows)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[("Topic", "note.md")], [0, 1])

    def test_no_duplicates(self):
        rows = [make_insight(), make_insight(topic="Другая")]
        self.assertEqual(find_duplicates(rows), {})

    def test_clean_removes_junk_and_dups(self):
        rows = [
            make_insight(),
            make_insight(),
            make_insight(topic="Unknown"),
            make_insight(topic="Третья"),
        ]
        kept, stats = clean_insights(rows)
        self.assertEqual(len(kept), 2)
        self.assertEqual(stats["junk"], 1)
        self.assertEqual(stats["duplicates"], 1)
        self.assertEqual(stats["kept"], 2)
        self.assertEqual(stats["total"], 4)

    def test_clean_does_not_mutate_input(self):
        rows = [make_insight(), make_insight()]
        before = json.dumps(rows, sort_keys=True)
        clean_insights(rows)
        self.assertEqual(json.dumps(rows, sort_keys=True), before)

    def test_clean_empty_input(self):
        kept, stats = clean_insights([])
        self.assertEqual(kept, [])
        self.assertEqual(stats["junk"], 0)


# -------------------------------------------------------------------- граф

class TestTokens(unittest.TestCase):
    def test_drops_stopwords(self):
        self.assertNotIn("the", tokens_of("the art of programming"))
        self.assertNotIn("и", tokens_of("граф и знание"))

    def test_drops_short_tokens(self):
        self.assertEqual(tokens_of("go go"), set())

    def test_keeps_significant(self):
        self.assertIn("graph", tokens_of("Graph Engineering Fundamentals"))

    def test_lowercases(self):
        self.assertIn("graph", tokens_of("GRAPH"))


class TestBuildGraph(unittest.TestCase):
    def test_same_source_edge(self):
        rows = [make_insight(topic="A", source_url="n.md"),
                make_insight(topic="B", source_url="n.md")]
        g = build_graph(rows, edge_types=("same_source",))
        self.assertEqual(g["edges"], [("n0000", "n0001", "same_source")])

    def test_same_topic_edge(self):
        rows = [make_insight(topic="A", source_url="1.md"),
                make_insight(topic="A", source_url="2.md")]
        g = build_graph(rows, edge_types=("same_topic",))
        self.assertEqual(len(g["edges"]), 1)
        self.assertEqual(g["edges"][0][2], "same_topic")

    def test_shares_tag_edge(self):
        rows = [make_insight(topic="A", tags=["ml"]),
                make_insight(topic="B", tags=["ml"])]
        g = build_graph(rows, edge_types=("shares_tag",))
        self.assertEqual(len(g["edges"]), 1)

    def test_no_edge_between_unrelated(self):
        rows = [make_insight(topic="A", tags=["x"]),
                make_insight(topic="B", tags=["y"])]
        g = build_graph(rows, edge_types=("shares_tag",))
        self.assertEqual(g["edges"], [])

    def test_edge_deduplicated_across_types(self):
        rows = [make_insight(topic="A", source_url="n.md", tags=["ml"], category="A"),
                make_insight(topic="B", source_url="n.md", tags=["ml"], category="B")]
        g = build_graph(rows)
        pairs = {(u, v) for u, v, _ in g["edges"]}
        self.assertEqual(pairs, {("n0000", "n0001")})
        self.assertEqual(len(g["edges"]), 2)

    def test_degree_sum_equals_twice_edges(self):
        rows = [make_insight(topic=f"T{i}", source_url=f"{i}.md", tags=[f"g{i}"])
                for i in range(6)]
        rows.append(make_insight(topic="X", source_url="x.md", tags=["gx"]))
        g = build_graph(rows)
        m = metrics(g)
        self.assertEqual(sum(m["degrees"].values()), 2 * m["edges"])

    def test_isolated_detected(self):
        rows = [make_insight(topic="A", source_url="1.md", tags=["a"], category="A"),
                make_insight(topic="B", source_url="2.md", tags=["b"], category="B")]
        g = build_graph(rows)
        self.assertEqual(sorted(g["isolated"]), ["n0000", "n0001"])

    def test_constant_tags_are_suppressed(self):
        rows = [make_insight(topic=f"T{i}", tags=["learned"]) for i in range(10)]
        g = build_graph(rows)
        self.assertEqual(g["edges"], [])
        self.assertTrue(any(s["kind"] == "shares_tag" for s in g["suppressed"]))

    def test_token_overlap_edge(self):
        rows = [make_insight(topic="Graph Engineering Fundamentals", tags=[], category=""),
                make_insight(topic="Graph Engineering Advanced", tags=[], category="")]
        g = build_graph(rows, edge_types=("token_overlap",))
        self.assertEqual(len(g["edges"]), 1)

    def test_token_overlap_below_threshold(self):
        rows = [make_insight(topic="Graph Engineering", tags=[], category=""),
                make_insight(topic="Rust Networking", tags=[], category="")]
        g = build_graph(rows, edge_types=("token_overlap",), min_shared=2)
        self.assertEqual(g["edges"], [])

    def test_token_overlap_three_shared_words_meets_threshold(self):
        rows = [make_insight(topic="Graph Engineering RAG", tags=[], category=""),
                make_insight(topic="Graph Engineering Agents", tags=[], category="")]
        g = build_graph(rows, edge_types=("token_overlap",), min_shared=3)
        self.assertEqual(len(g["edges"]), 1)

    def test_empty_corpus(self):
        g = build_graph([])
        self.assertEqual(g["nodes"], [])
        self.assertEqual(g["edges"], [])
        m = metrics(g)
        self.assertEqual(m["density"], 0.0)
        self.assertEqual(m["components"], 0)

    def test_real_corpus_graph_is_not_complete(self):
        kept, _ = clean_insights(list(iter_insights(load_all(REAL_MEMORY))))
        g = build_graph(kept)
        m = metrics(g)
        self.assertEqual(m["nodes"], 100)
        self.assertLess(m["density"], 0.1)


class TestMetrics(unittest.TestCase):
    def test_two_triangles_two_components(self):
        # i%2 на 6 элементах даёт две группы по 3 — два треугольника.
        rows = [make_insight(topic=f"T{i}", source_url=f"{i}.md", tags=[f"g{i%2}"],
                             category=f"C{i%2}") for i in range(6)]
        g = build_graph(rows, edge_types=("shares_tag",))
        m = metrics(g)
        self.assertEqual(m["components"], 2)
        self.assertEqual(m["largest_component"], 3)

    def test_centrality_orders_connected_group_first(self):
        # Группа из 4 узлов при 10 узлах в корпусе не подавляется (порог 5),
        # поэтому 4 узла образуют клику и обязаны стоять выше изолированных.
        rows = [make_insight(topic=f"Core{i}", source_url=f"c{i}.md",
                             tags=["core"], category=f"Core{i}") for i in range(4)]
        for i in range(6):
            rows.append(make_insight(topic=f"Solo{i}", source_url=f"s{i}.md",
                                     tags=[f"u{i}"], category=f"Solo{i}"))
        g = build_graph(rows, edge_types=("shares_tag",))
        top = centrality(g, top=4)
        self.assertEqual({row["topic"] for row in top},
                         {"Core0", "Core1", "Core2", "Core3"})
        self.assertTrue(all(row["degree"] == 3 for row in top))
        self.assertEqual(g["isolated"], sorted(f"n{i:04d}" for i in range(4, 10)))

    def test_density_zero_without_edges(self):
        rows = [make_insight(topic=f"T{i}", source_url=f"{i}.md", tags=[f"g{i}"])
                for i in range(4)]
        self.assertEqual(metrics(build_graph(rows))["density"], 0.0)

    def test_edge_type_counts(self):
        rows = [make_insight(topic="A", source_url="n.md"),
                make_insight(topic="B", source_url="n.md")]
        counts = edge_type_counts(build_graph(rows, edge_types=("same_source", "same_topic")))
        self.assertEqual(counts, {"same_source": 1})

    def test_centrality_respects_limit(self):
        rows = [make_insight(topic=f"T{i}", source_url=f"{i}.md", tags=[f"g{i}"])
                for i in range(5)]
        self.assertEqual(len(centrality(build_graph(rows), top=2)), 2)


class TestQuery(unittest.TestCase):
    def setUp(self):
        rows = [make_insight(topic="Graph Engineering", tags=["graph"], relevance_score=0.9),
                make_insight(topic="Rust Networking", tags=["net"], relevance_score=0.5)]
        self.g = build_graph(rows)

    def test_finds_by_topic(self):
        hits = graph_query(self.g, "graph")
        self.assertEqual(hits[0]["topic"], "Graph Engineering")

    def test_finds_by_tag(self):
        self.assertEqual(graph_query(self.g, "net")[0]["topic"], "Rust Networking")

    def test_empty_query(self):
        self.assertEqual(graph_query(self.g, "   "), [])

    def test_no_match(self):
        self.assertEqual(graph_query(self.g, "zzzznotfound"), [])

    def test_limit_respected(self):
        self.assertEqual(len(graph_query(self.g, "a", limit=1)), 1)

    def test_real_corpus_query_graph(self):
        kept, _ = clean_insights(list(iter_insights(load_all(REAL_MEMORY))))
        hits = graph_query(build_graph(kept), "graph", limit=5)
        self.assertGreater(len(hits), 0)

    def test_real_corpus_query_nonsense(self):
        kept, _ = clean_insights(list(iter_insights(load_all(REAL_MEMORY))))
        self.assertEqual(graph_query(build_graph(kept), "квантошабаника"), [])


# --------------------------------------------------------------------- CLI

class TestCLI(TempDirCase):
    def corpus(self):
        write_memory(self.dir, "professor_insights_cycle_001.json", 1,
                     [make_insight(), make_insight(topic="Unknown"), make_insight()])
        return ["--memory-dir", str(self.dir)]

    def test_report_ok(self):
        code = main(self.corpus() + ["report"])
        self.assertEqual(code, EXIT_OK)

    def test_report_json_valid(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(self.corpus() + ["report", "--json"])
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["insights_total"], 3)
        self.assertEqual(payload["junk"], 1)

    def test_validate_exit_data_on_problems(self):
        path = write_memory(self.dir, "professor_insights_cycle_001.json", 1,
                            [make_insight(topic=5)])
        code = main(["--memory-dir", str(self.dir), "validate"])
        self.assertEqual(code, EXIT_DATA)

    def test_validate_ok_on_clean(self):
        self.assertEqual(main(self.corpus() + ["validate"]), EXIT_OK)

    def test_dedupe_dry_run_writes_nothing(self):
        args = self.corpus()
        before = sorted(p.name for p in self.dir.iterdir())
        code = main(args + ["dedupe"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)

    def test_dedupe_fix_writes_bak(self):
        code = main(self.corpus() + ["dedupe", "--fix"])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(list(self.dir.glob("*.bak")))

    def test_dedupe_fix_removes_junk(self):
        main(self.corpus() + ["dedupe", "--fix"])
        data = load(self.dir / "professor_insights_cycle_001.json")
        self.assertEqual(len(data["insights"]), 1)
        self.assertEqual(data["total_insights"], 1)

    def test_graph_ok(self):
        self.assertEqual(main(self.corpus() + ["graph"]), EXIT_OK)

    def test_graph_unknown_type_is_usage_error(self):
        code = main(self.corpus() + ["graph", "--types", "nonsense"])
        self.assertEqual(code, EXIT_USAGE)

    def test_graph_min_shared_flag(self):
        self.assertEqual(main(self.corpus() + ["graph", "--min-shared", "3"]), EXIT_OK)

    def test_query_hit_and_miss(self):
        self.assertEqual(main(self.corpus() + ["query", "Topic"]), EXIT_OK)
        self.assertEqual(main(self.corpus() + ["query", "zzzznotfound"]), EXIT_OK)

    def test_no_command_prints_help(self):
        self.assertEqual(main(["--memory-dir", str(self.dir)]), EXIT_USAGE)

    def test_bad_memory_dir_is_usage_error(self):
        code = main(["--memory-dir", str(self.dir / "нет"), "report"])
        self.assertEqual(code, EXIT_USAGE)

    def test_edge_types_constant_covers_cli_default(self):
        self.assertIn("token_overlap", EDGE_TYPES)

    def test_node_id_format(self):
        self.assertEqual(node_id(7), "n0007")


class TestGraphReport(TempDirCase):
    """Пункт 12 плана: числа GRAPH_REPORT.md обязаны совпадать с прогоном CLI."""

    def write_corpus(self):
        rows = []
        for i in range(12):
            rows.append(make_insight(
                topic=f"Тема {i}",
                summary=f"сводка {i}",
                category="Учебник" if i < 6 else "Заметки",
                tags=["общий"] if i < 6 else [f"у{i}"],
                source_url=f"{i}.md",
            ))
        rows.append(make_insight(topic="Unknown"))
        write_memory(self.dir, "professor_insights_cycle_001.json", 1, rows)
        return ["--memory-dir", str(self.dir)]

    def generate(self, name="GRAPH_REPORT.md"):
        args = self.write_corpus() + ["graph-report", "--out", str(self.dir / name)]
        self.assertEqual(main(args), EXIT_OK)
        return (self.dir / name).read_text(encoding="utf-8")

    def test_report_is_written(self):
        text = self.generate()
        self.assertIn("# Граф знаний", text)

    def test_report_numbers_match_cli(self):
        text = self.generate()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(self.write_corpus() + ["graph", "--json"])
        payload = json.loads(buf.getvalue())
        self.assertIn(f"- узлов: {payload['nodes']}", text)
        self.assertIn(f"- рёбер: {payload['edges']}", text)
        self.assertIn(f"- плотность: {payload['density']}", text)
        self.assertIn(f"- компонент связности: {payload['components']}", text)
        self.assertIn(f"- изолированных узлов: {payload['isolated_count']}", text)

    def test_report_is_reproducible(self):
        first = self.generate()
        second = self.generate()
        self.assertEqual(first, second)

    def test_report_records_corpus_counts(self):
        text = self.generate()
        self.assertIn("- записей всего: 13", text)
        self.assertIn("- записей после очистки: 12", text)

    def test_report_lists_suppressed_keys(self):
        text = self.generate()
        self.assertIn("## Подавленные неразличающие ключи", text)

    def test_report_has_sensitivity_table(self):
        text = self.generate()
        self.assertIn("## Чувствительность к порогу", text)
        self.assertIn("| min_shared |", text)

    def test_conclusions_do_not_mention_foreign_topics(self):
        """Выводы должны выводиться из данных, а не быть расписанным текстом.

        Регрессия: раздел выводов однажды содержал «пять томов TAOCP» и «83
        изолированных» руками, и на чужом корпусе отчёт печатал неправду.
        """
        text = self.generate()
        self.assertNotIn("TAOCP", text)
        self.assertNotIn("Art of Computer Programming", text)
        self.assertNotIn("professor_sync.py начнёт различать теги и категории по темам,"
                         " добавятся", text.replace("\n", " "))

    def test_conclusions_quote_real_counts(self):
        text = self.generate()
        self.assertIn("## Что из этого следует", text)
        self.assertIn("изолированных узлов", text.lower())

    def test_conclusions_state_no_write_happened(self):
        self.assertIn("Данные не изменялись", self.generate())

    def test_report_on_real_corpus_matches_real_cli(self):
        from contextlib import redirect_stdout
        import io
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--memory-dir", str(REAL_MEMORY), "graph-report",
                       "--out", str(self.dir / "REAL.md")])
        self.assertEqual(rc, EXIT_OK)
        text = (self.dir / "REAL.md").read_text(encoding="utf-8")
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            main(["--memory-dir", str(REAL_MEMORY), "graph", "--json"])
        payload = json.loads(buf2.getvalue())
        self.assertIn(f"- узлов: {payload['nodes']}", text)
        self.assertIn(f"- рёбер: {payload['edges']}", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
