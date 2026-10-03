"""Тесты пунктов 5, 6, 7, 9, 10: метрики, поиск, канонизация, отчёт, канарейка, CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p4_provenance import (  # noqa: E402
    attribution,
    canon,
    canary,
    cli,
    fingerprint,
    loader,
    metrics,
    paths,
    report,
)

REPO = Path(__file__).resolve().parent.parent.parent


def _record(**overrides):
    base = {
        "topic": "Тема",
        "category": "AI Engineering",
        "summary": "Краткое описание",
        "source_type": "web",
        "relevance_score": 0.8,
        "applicable_projects": [4],
        "tags": ["corpus"],
        "timestamp": "2026-08-16T08:10:34",
        "source_url": "https://example.org/a",
        "_cycle": 1,
        "_source_file": "professor_insights_cycle_001.json",
    }
    base.update(overrides)
    return base


def _write_memory(directory: Path, records, project=4, cycle=1, name=None):
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle": cycle,
        "project": project,
        "synced_at": "2026-08-16T08:10:34.037654+00:00",
        "total_insights": len(records),
        "insights": records,
    }
    path = directory / (name or f"professor_insights_cycle_{cycle:03d}.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# пункт 5 — метрики
# --------------------------------------------------------------------------


class TestMetrics:
    def test_records_match_loader(self):
        records = loader.iter_records()
        assert metrics.metrics(records)["records"] == len(records)

    def test_per_cycle_sums_to_total(self):
        report = metrics.metrics(loader.iter_records())
        assert sum(report["per_cycle"].values()) == report["records"]

    def test_cycles_counted(self):
        report = metrics.metrics(loader.iter_records())
        assert report["cycle_count"] == len(report["cycles"])
        assert report["cycle_count"] >= 1

    def test_unique_topics_match_repetition_report(self):
        records = loader.iter_records()
        assert (
            metrics.metrics(records)["unique_topics"]
            == attribution.repetition_report(records)["unique_topics"]
        )

    def test_empty_topics_detected(self):
        report = metrics.metrics([_record(topic=""), _record(topic="   ")])
        assert report["empty_topics"] == 2
        assert len(report["empty_topic_examples"]) == 2

    def test_no_empty_topics_in_real_corpus(self):
        assert metrics.metrics(loader.iter_records())["empty_topics"] == 0

    def test_missing_fields_counted(self):
        report = metrics.metrics([_record(source_url="")])
        assert report["missing_fields"]["source_url"] == 1
        assert report["missing_fields"]["topic"] == 0

    def test_relevance_histogram_sums_to_total(self):
        report = metrics.metrics(loader.iter_records())
        assert sum(report["relevance"].values()) == report["records"]

    def test_relevance_histogram_buckets(self):
        report = metrics.metrics([_record(relevance_score=0.95), _record(relevance_score=0.55)])
        assert report["relevance"]["0.9"] == 1
        assert report["relevance"]["0.5"] == 1

    def test_bool_score_goes_to_zero_bucket(self):
        report = metrics.metrics([_record(relevance_score=True)])
        assert report["relevance"]["0.0"] == 1

    def test_verdict_present(self):
        assert metrics.metrics(loader.iter_records())["verdict"]

    def test_empty_corpus(self):
        report = metrics.metrics([])
        assert report["records"] == 0
        assert report["relevance"] == {}

    def test_source_types_present(self):
        assert metrics.metrics(loader.iter_records())["source_types"]


# --------------------------------------------------------------------------
# пункт 6 — поиск и фильтры
# --------------------------------------------------------------------------


class TestFilters:
    def test_empty_filters_return_all(self):
        records = [_record(), _record(topic="Другая")]
        assert len(metrics.filter_records(records)) == 2

    def test_topic_filter(self):
        records = [_record(topic="Графы"), _record(topic="Кванты")]
        assert len(metrics.filter_records(records, topic="граф")) == 1

    def test_category_filter(self):
        records = [_record(category="Textbook"), _record(category="UI")]
        assert len(metrics.filter_records(records, category="text")) == 1

    def test_source_type_filter(self):
        records = [_record(source_type="textbook"), _record(source_type="web")]
        assert len(metrics.filter_records(records, source_type="textbook")) == 1

    def test_cycle_filter(self):
        records = [_record(_cycle=1), _record(_cycle=2)]
        assert len(metrics.filter_records(records, cycle=2)) == 1

    def test_tag_filter(self):
        records = [_record(tags=["a", "b"]), _record(tags=["c"])]
        assert len(metrics.filter_records(records, tags=["b"])) == 1

    def test_tag_filter_multiple_any(self):
        records = [_record(tags=["a"]), _record(tags=["b"])]
        assert len(metrics.filter_records(records, tags=["a", "b"])) == 2

    def test_min_score_filter(self):
        records = [_record(relevance_score=0.5), _record(relevance_score=0.9)]
        assert len(metrics.filter_records(records, min_score=0.8)) == 1

    def test_max_score_filter(self):
        records = [_record(relevance_score=0.5), _record(relevance_score=0.9)]
        assert len(metrics.filter_records(records, max_score=0.6)) == 1

    def test_score_range(self):
        records = [_record(relevance_score=0.1), _record(relevance_score=0.5), _record(relevance_score=0.9)]
        assert len(metrics.filter_records(records, min_score=0.2, max_score=0.8)) == 1

    def test_impossible_range_empty(self):
        records = [_record(relevance_score=0.5)]
        assert metrics.filter_records(records, min_score=0.9) == []

    def test_combined_filters(self):
        records = [
            _record(topic="Граф", category="Textbook", relevance_score=0.9),
            _record(topic="Граф", category="UI", relevance_score=0.9),
            _record(topic="Квант", category="Textbook", relevance_score=0.9),
        ]
        found = metrics.filter_records(records, topic="граф", category="textbook")
        assert len(found) == 1

    def test_filter_on_real_corpus_not_empty(self):
        records = loader.iter_records()
        by_category = metrics.filter_records(records, category="textbook")
        assert by_category, "фильтр по категории textbook обязан что-то найти"


class TestSearch:
    def test_empty_query_returns_nothing(self):
        assert metrics.search(loader.iter_records(), "") == []

    def test_finds_on_real_corpus(self):
        hits = metrics.search(loader.iter_records(), "graph", limit=5)
        assert hits
        assert len(hits) <= 5

    def test_exact_topic_ranks_first(self):
        records = [
            _record(topic="Graph Engineering", relevance_score=0.5),
            _record(topic="Другое", summary="graph внутри", relevance_score=0.9),
        ]
        hits = metrics.search(records, "graph engineering")
        assert hits[0]["record"]["topic"] == "Graph Engineering"
        assert hits[0]["weight"] == 1.0

    def test_prefix_beats_contains(self):
        records = [
            _record(topic="Продолжение graph"),
            _record(topic="graph в начале"),
        ]
        hits = metrics.search(records, "graph")
        assert hits[0]["weight"] > hits[1]["weight"]

    def test_zero_weight_dropped(self):
        records = [_record(topic="Совсем другое")]
        assert metrics.search(records, "graph") == []

    def test_summary_match_lowest_weight(self):
        records = [_record(topic="Тема", summary="упоминается graph тут")]
        hits = metrics.search(records, "graph")
        assert hits[0]["weight"] == 0.3

    def test_relevance_breaks_tie(self):
        records = [
            _record(topic="graph тема", relevance_score=0.5),
            _record(topic="graph тема", relevance_score=0.9),
        ]
        hits = metrics.search(records, "graph тема")
        assert hits[0]["record"]["relevance_score"] == 0.9

    def test_limit_respected(self):
        hits = metrics.search(loader.iter_records(), "graph", limit=3)
        assert len(hits) == 3

    def test_limit_zero(self):
        assert metrics.search(loader.iter_records(), "graph", limit=0) == []

    def test_search_summary_shape(self):
        summary = metrics.search_summary(loader.iter_records(), "graph")
        assert summary["query"] == "graph"
        assert summary["hits"] > 0
        assert len(summary["top"]) <= 10

    def test_search_with_filter(self):
        summary = metrics.search_summary(
            loader.iter_records(), "graph", category="textbook"
        )
        assert summary["filters"]["category"] == "textbook"
        assert summary["hits"] > 0

    def test_search_is_case_insensitive(self):
        assert metrics.search(loader.iter_records(), "GRAPH")
        assert metrics.search(loader.iter_records(), "Graph")


class TestUniqueFilterValues:
    def test_values_from_data(self):
        values = metrics.unique_filter_values(loader.iter_records())
        assert "Textbook" in values["categories"]
        assert "textbook" in values["source_types"]
        assert values["tags"]

    def test_empty_corpus(self):
        values = metrics.unique_filter_values([])
        assert values["categories"] == []


# --------------------------------------------------------------------------
# пункт 7 — канонизация
# --------------------------------------------------------------------------


class TestNormalise:
    def test_case_folded(self):
        assert canon.normalise_text("Graph Engineering") == "graph engineering"

    def test_punctuation_dropped(self):
        assert canon.normalise_text("Graph, Engineering!") == "graph engineering"

    def test_dashes_folded(self):
        assert canon.normalise_text("multi-agent systems") == "multi-agent systems"
        assert canon.normalise_text("multi–agent systems") == canon.normalise_text("multi-agent systems")

    def test_whitespace_squashed(self):
        assert canon.normalise_text("  много   пробелов ") == "много пробелов"

    def test_url_scheme_dropped(self):
        assert canon.normalise_url("https://example.org/a") == canon.normalise_url("http://example.org/a")

    def test_url_www_dropped(self):
        assert canon.normalise_url("https://www.example.org/a") == "example.org/a"

    def test_url_trailing_slash_dropped(self):
        assert canon.normalise_url("https://example.org/a/") == "example.org/a"


class TestCanonKey:
    def test_same_topic_different_case(self):
        assert canon.canon_key(_record(topic="Graph X")) == canon.canon_key(_record(topic="graph x"))

    def test_different_url_different_key(self):
        assert canon.canon_key(_record()) != canon.canon_key(_record(source_url="https://b"))

    def test_different_category_different_key(self):
        assert canon.canon_key(_record()) != canon.canon_key(_record(category="UI"))


class TestCanonicalise:
    def test_exact_duplicates_collapse(self):
        canonical = canon.canonicalise([_record(), _record()])
        assert canonical["records_in"] == 2
        assert canonical["canonical_out"] == 1
        assert canonical["duplicate_records"] == 1
        assert canonical["records"][0]["_occurrences"] == 2

    def test_no_duplicates_leaves_all(self):
        canonical = canon.canonicalise([_record(), _record(topic="Иная")])
        assert canonical["canonical_out"] == 2
        assert canonical["duplicate_records"] == 0
        assert canonical["dedup_ratio"] == 0.0

    def test_case_variants_collapse(self):
        canonical = canon.canonicalise([_record(topic="Graph X"), _record(topic="graph x")])
        assert canonical["canonical_out"] == 1

    def test_higher_relevance_wins(self):
        canonical = canon.canonicalise(
            [_record(relevance_score=0.5), _record(relevance_score=0.95)]
        )
        assert canonical["records"][0]["relevance_score"] == 0.95

    def test_later_cycle_wins_on_tie(self):
        canonical = canon.canonicalise([_record(_cycle=1), _record(_cycle=5)])
        assert canonical["records"][0]["_cycle"] == 5

    def test_sources_recorded(self):
        canonical = canon.canonicalise([_record(_cycle=1), _record(_cycle=5)])
        sources = canonical["records"][0]["_sources"]
        assert len(sources) == 2
        assert any("cycle-5" in s for s in sources)

    def test_blank_topics_not_merged(self):
        canonical = canon.canonicalise([_record(topic=""), _record(topic="")])
        assert canonical["canonical_out"] == 2

    def test_real_corpus_dedups(self):
        canonical = canon.canonicalise(loader.iter_records())
        assert canonical["canonical_out"] < canonical["records_in"]
        assert canonical["duplicate_records"] > 0
        assert canonical["records_in"] == len(loader.iter_records())

    def test_duplicates_listed(self):
        canonical = canon.canonicalise(loader.iter_records())
        assert canonical["duplicate_groups"] == len(canonical["duplicates"])
        assert canonical["duplicates"][0]["occurrences"] >= 2

    def test_dedup_ratio_consistent(self):
        canonical = canon.canonicalise(loader.iter_records())
        expected = canonical["duplicate_records"] / canonical["records_in"]
        assert canonical["dedup_ratio"] == pytest.approx(expected)

    def test_sorted_by_occurrences(self):
        canonical = canon.canonicalise(loader.iter_records())
        counts = [r["_occurrences"] for r in canonical["records"]]
        assert counts == sorted(counts, reverse=True)

    def test_empty_input(self):
        canonical = canon.canonicalise([])
        assert canonical["records_in"] == 0
        assert canonical["records"] == []


class TestOnlyMine:
    def test_all_shared(self):
        records = [_record()]
        canonical = canon.canonicalise(records)
        result = canon.only_mine(canonical, list(records))
        assert result["own_records"] == 0

    def test_half_shared(self):
        canonical = canon.canonicalise([_record(), _record(topic="Своё")])
        result = canon.only_mine(canonical, [_record()])
        assert result["own_records"] == 1
        assert result["topics"] == ["Своё"]

    def test_share_computed(self):
        canonical = canon.canonicalise([_record(), _record(topic="Своё")])
        result = canon.only_mine(canonical, [_record()])
        assert result["share"] == 0.5


class TestWriteCanonicalJson:
    def test_writes_inside_project(self):
        """Путь задаётся относительно корня Project4 — так и работает запись."""
        canonical = canon.canonicalise([_record()])
        target = paths.PROJECT_DIR / "artifacts" / "test_canonical.json"
        try:
            canon.write_canonical_json(canonical, "artifacts/test_canonical.json")
            assert target.exists()
            data = json.loads(target.read_text(encoding="utf-8"))
            assert data["canonical_out"] == 1
        finally:
            target.unlink(missing_ok=True)

    def test_refuses_outside_root(self):
        canonical = canon.canonicalise([_record()])
        with pytest.raises(paths.PathOutsideProject):
            canon.write_canonical_json(canonical, "../Project3/evil.json")

    def test_refuses_absolute(self):
        canonical = canon.canonicalise([_record()])
        with pytest.raises(paths.PathOutsideProject):
            canon.write_canonical_json(canonical, "/tmp/evil-p4.json")


# --------------------------------------------------------------------------
# пункт 10 — канарейка
# --------------------------------------------------------------------------


class TestCanary:
    def test_real_tree_reports_drift(self):
        report = canary.canary(loader.DEFAULT_DIR, REPO)
        assert report["status"] == canary.DRIFT

    def test_real_tree_names_the_cause(self):
        report = canary.canary(loader.DEFAULT_DIR, REPO)
        assert any("адресация сломана" in p for p in report["problems"])
        assert any("совпадает с" in p for p in report["problems"])

    def test_real_tree_counts_match_loader(self):
        report = canary.canary(loader.DEFAULT_DIR, REPO)
        assert report["records"] == len(loader.iter_records())
        assert report["default_addressed"] == report["records"]

    def test_real_tree_checks_two_of_three_fail(self):
        """Корпус валиден, но адресация сломана и тело не уникально."""
        report = canary.canary(loader.DEFAULT_DIR, REPO)
        assert report["checks"]["корпус валиден"] is True
        assert report["checks"]["адресация не дефолтная"] is False
        assert report["checks"]["тело уникально для Project4"] is False

    def test_separated_tree_reports_ok(self, tmp_path):
        mine = tmp_path / "memory"
        other = tmp_path / "Project1" / "memory"
        _write_memory(mine, [_record(applicable_projects=[4])])
        _write_memory(other, [_record(topic="Своё", applicable_projects=[1])])
        report = canary.canary(mine, tmp_path, names=["Project1"])
        assert report["status"] == canary.OK
        assert all(report["checks"].values())

    def test_empty_corpus_is_drift(self, tmp_path):
        report = canary.canary(tmp_path, tmp_path, names=[])
        assert report["status"] == canary.DRIFT
        assert any("пуст" in p for p in report["problems"])

    def test_invalid_corpus_is_drift(self, tmp_path):
        memory = tmp_path / "memory"
        memory.mkdir(parents=True)
        (memory / "professor_insights_cycle_001.json").write_text(
            json.dumps({"cycle": 1, "project": 9, "total_insights": 1,
                        "insights": [{"topic": "t"}]}),
            encoding="utf-8",
        )
        report = canary.canary(tmp_path, tmp_path, names=[])
        assert report["status"] == canary.DRIFT

    def test_exit_code(self):
        drift = canary.canary(loader.DEFAULT_DIR, REPO)
        assert canary.exit_code(drift) == 1
        assert canary.exit_code({"status": canary.OK}) == 0

    def test_line_is_single_line(self):
        text = canary.line(canary.canary(loader.DEFAULT_DIR, REPO))
        assert "\n" not in text
        assert text.startswith("DRIFT:")

    def test_threshold_respected(self, tmp_path):
        memory = tmp_path / "memory"
        _write_memory(memory, [_record(applicable_projects=[1, 2, 3, 4])])
        strict = canary.canary(memory, tmp_path, names=[], default_share_threshold=0.0)
        lenient = canary.canary(memory, tmp_path, names=[], default_share_threshold=1.0)
        assert strict["status"] == canary.DRIFT
        assert lenient["status"] == canary.OK


# --------------------------------------------------------------------------
# пункт 9 — отчёт
# --------------------------------------------------------------------------


class TestReport:
    def test_renders(self):
        text = report.render_report(loader.DEFAULT_DIR, REPO)
        assert text.startswith("# PROVENANCE_REPORT.md")
        assert "Живое воспроизведение дефекта" in text

    def test_numbers_come_from_data(self):
        text = report.render_report(loader.DEFAULT_DIR, REPO)
        facts = report.report_facts(loader.DEFAULT_DIR, REPO)
        assert f"| Записей всего | {facts['records']} |" in text
        assert f"| Циклов | {facts['cycles']} |" in text

    def test_identity_named(self):
        text = report.render_report(loader.DEFAULT_DIR, REPO)
        for name in ("Project1", "Project2", "Project3"):
            assert name in text

    def test_defect_confirmed_in_report(self):
        text = report.render_report(loader.DEFAULT_DIR, REPO)
        assert "Дефект подтверждён: да" in text

    def test_own_scope_declared(self):
        text = report.render_report(loader.DEFAULT_DIR, REPO)
        assert "не скоум Project4" in text

    def test_without_repro(self):
        text = report.render_report(loader.DEFAULT_DIR, REPO, repro_enabled=False)
        assert "Живое воспроизведение" not in text

    def test_facts_consistent_with_modules(self):
        facts = report.report_facts(loader.DEFAULT_DIR, REPO)
        assert facts["records"] == len(loader.iter_records())
        assert facts["valid"] is True
        assert set(facts["identity"]) == {"Project1", "Project2", "Project3"}
        assert facts["addressing"] == 1.0

    def test_report_on_separated_tree(self, tmp_path):
        mine = tmp_path / "Project4" / "memory"
        other = tmp_path / "Project1" / "memory"
        _write_memory(mine, [_record(applicable_projects=[4])])
        _write_memory(other, [_record(topic="Своё", applicable_projects=[1])])
        text = report.render_report(mine, tmp_path, names=["Project1"], repro_enabled=False)
        assert "Project4 идентичен: никому" in text

    def test_table_renders(self):
        table = report._table(["A", "B"], [[1, 2]])
        assert table.splitlines()[0] == "| A | B |"
        assert "---" in table.splitlines()[1]


# --------------------------------------------------------------------------
# пункт 8 — CLI
# --------------------------------------------------------------------------


class TestCli:
    def _run(self, argv):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_validate(self):
        code, out = self._run(["validate"])
        assert code == 0
        assert json.loads(out)["valid"] is True

    def test_load(self):
        path = sorted(loader.discover(loader.DEFAULT_DIR))[0]
        code, out = self._run(["load", str(path)])
        assert code == 0
        assert json.loads(out)["records"] > 0

    def test_load_bad_file(self, capsys):
        code, _ = self._run(["load", "/tmp/definitely-not-here-p4.json"])
        assert code == 1

    def test_fingerprint(self):
        code, out = self._run(["fingerprint"])
        assert code == 0
        assert json.loads(out)

    def test_repro(self):
        code, out = self._run(["repro"])
        assert code == 0
        assert json.loads(out)["defect_confirmed"] is True

    def test_identity(self):
        code, out = self._run(["identity"])
        assert code == 0
        assert json.loads(out)["identical_with_all"] is True

    def test_audit(self):
        code, out = self._run(["audit"])
        assert code == 0
        data = json.loads(out)
        assert data["addressing"]["default_share"] == 1.0
        assert data["repetition"]["unique_topics"] > 0

    def test_metrics(self):
        code, out = self._run(["metrics"])
        assert code == 0
        assert json.loads(out)["records"] > 0

    def test_search(self):
        code, out = self._run(["search", "graph"])
        assert code == 0
        assert json.loads(out)["hits"] > 0

    def test_search_with_filters(self):
        code, out = self._run(["search", "graph", "--category", "textbook", "--min-score", "0.8"])
        assert code == 0
        assert json.loads(out)["hits"] > 0

    def test_fields(self):
        code, out = self._run(["fields"])
        assert code == 0
        assert json.loads(out)["categories"]

    def test_canon(self):
        code, out = self._run(["canon"])
        assert code == 0
        data = json.loads(out)
        assert data["duplicate_records"] > 0
        assert len(data["top"]) == 10

    def test_canon_with_neighbour(self):
        code, out = self._run(["canon", "--neighbour", "Project1"])
        assert code == 0
        assert "own_vs_neighbour" in json.loads(out)

    def test_canon_missing_neighbour(self):
        code, out = self._run(["canon", "--neighbour", "Project9"])
        assert code == 0
        assert "error" in json.loads(out)["own_vs_neighbour"]

    def test_canary_drift_exit_one(self):
        code, out = self._run(["canary"])
        assert code == 1
        assert out.startswith("DRIFT:")

    def test_canary_json(self):
        code, out = self._run(["canary", "--json"])
        assert code == 1
        assert '"status": "DRIFT"' in out

    def test_report_stdout(self):
        code, out = self._run(["report"])
        assert code == 0
        assert out.startswith("# PROVENANCE_REPORT.md")

    def test_report_to_file(self, tmp_path):
        target = tmp_path / "report.md"
        code, out = self._run(["report", "--out", str(target)])
        assert code == 0
        assert target.read_text(encoding="utf-8").startswith("# PROVENANCE_REPORT.md")
        assert "отчёт записан" in out

    def test_validate_bad_corpus_exit_one(self, tmp_path):
        (tmp_path / "professor_insights_cycle_001.json").write_text("{oops", encoding="utf-8")
        code, _ = self._run(["-m", str(tmp_path), "validate"])
        assert code == 1

    def test_memory_override(self, tmp_path):
        _write_memory(tmp_path, [_record()])
        code, out = self._run(["-m", str(tmp_path), "validate"])
        assert code == 0
        assert json.loads(out)["records"] == 1

    def test_every_command_registered(self):
        from p4_provenance.cli import build_parser

        parser = build_parser()
        sub = next(a for a in parser._actions if a.dest == "command")
        for name in ("validate", "load", "fingerprint", "repro", "identity",
                     "audit", "metrics", "search", "fields", "canon", "canary", "report"):
            assert name in sub.choices, f"команда {name} не зарегистрирована"

    def test_commands_have_handlers(self):
        for command in ("validate", "fingerprint", "repro", "identity", "audit",
                        "metrics", "search", "fields", "canon", "canary", "report"):
            parser = cli.build_parser()
            args = parser.parse_args([command] + (["graph"] if command == "search" else []))
            assert callable(getattr(args, "func", None)), command

    def test_load_command_needs_argument(self):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["load"])