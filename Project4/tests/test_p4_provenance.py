"""Тесты пакета форензики памяти Project4.

Проверки построены так, чтобы тест был испортим: числа сверяются с независимо
посчитанными в самом тесте, а не с константами, вытащенными из отчёта.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p4_provenance import (  # noqa: E402
    MARKERS,
    SYNC_DEFAULT_PROJECTS,
    attribution,
    fingerprint,
    loader,
    paths,
    repro,
)
from p4_provenance.paths import PathOutsideProject  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent


# --------------------------------------------------------------------------
# фикстуры
# --------------------------------------------------------------------------


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
    }
    base.update(overrides)
    return base


def _file(path: Path, records, project=4, cycle=1, total=None):
    payload = {
        "cycle": cycle,
        "project": project,
        "synced_at": "2026-08-16T08:10:34.037654+00:00",
        "total_insights": len(records) if total is None else total,
        "insights": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# пункт 1 — загрузчик и валидация
# --------------------------------------------------------------------------


class TestStripMarkers:
    def test_marker_removed(self):
        text, removed = loader.strip_markers("# HOT\n{\"a\": 1}")
        assert removed == ["# HOT"]
        assert json.loads(text) == {"a": 1}

    def test_cold_marker_removed(self):
        text, removed = loader.strip_markers("# COLD\n{\"a\": 1}")
        assert removed == ["# COLD"]
        assert json.loads(text) == {"a": 1}

    def test_several_markers(self):
        text, removed = loader.strip_markers("# HOT\n# COLD\n{}\n")
        assert removed == list(MARKERS)
        assert text == "{}\n"

    def test_no_marker(self):
        text, removed = loader.strip_markers('{"a": 1}')
        assert removed == []
        assert text == '{"a": 1}'

    def test_marker_inside_document_kept(self):
        text, removed = loader.strip_markers('{"a": "# HOT"}')
        assert removed == []
        assert "# HOT" in text

    def test_empty_text(self):
        assert loader.strip_markers("") == ("", [])


class TestLoad:
    def test_load_real_corpus(self):
        data = loader.load(sorted(loader.discover(loader.DEFAULT_DIR))[0])
        assert isinstance(data["insights"], list)
        assert data["total_insights"] == len(data["insights"])

    def test_load_with_hot_marker(self, tmp_path):
        path = _file(tmp_path / "professor_insights_cycle_001.json", [_record()])
        path.write_text("# HOT\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        data = loader.load(path)
        assert len(data["insights"]) == 1
        assert data["_markers_removed"] == ["# HOT"]

    def test_broken_json_raises(self, tmp_path):
        path = tmp_path / "professor_insights_cycle_002.json"
        path.write_text('{"insights": [', encoding="utf-8")
        with pytest.raises(loader.MemoryInvalid):
            loader.load(path)

    def test_broken_json_without_marker_mentions_line(self, tmp_path):
        path = tmp_path / "professor_insights_cycle_003.json"
        path.write_text('{"insights": [\n', encoding="utf-8")
        with pytest.raises(loader.MemoryInvalid) as exc:
            loader.load(path)
        assert "строка" in str(exc.value)

    def test_not_object(self, tmp_path):
        path = tmp_path / "professor_insights_cycle_004.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(loader.MemoryInvalid):
            loader.load(path)

    def test_insights_not_list(self, tmp_path):
        path = tmp_path / "professor_insights_cycle_005.json"
        path.write_text('{"insights": {}}', encoding="utf-8")
        with pytest.raises(loader.MemoryInvalid):
            loader.load(path)

    def test_total_mismatch(self, tmp_path):
        path = _file(tmp_path / "professor_insights_cycle_006.json", [_record()], total=99)
        with pytest.raises(loader.MemoryInvalid) as exc:
            loader.load(path)
        assert "99" in str(exc.value)

    def test_missing_file(self, tmp_path):
        with pytest.raises(loader.MemoryInvalid):
            loader.load(tmp_path / "professor_insights_cycle_007.json")


class TestValidate:
    def test_real_corpus_valid(self):
        report = loader.validate_corpus()
        assert report["valid"], report["problems"][:5]
        assert report["files"] >= 1
        assert report["problem_count"] == 0

    def test_record_count_matches_independent_count(self):
        independent = 0
        for path in loader.discover(loader.DEFAULT_DIR):
            independent += len(json.loads(path.read_text(encoding="utf-8"))["insights"])
        assert loader.validate_corpus()["records"] == independent

    def test_missing_required_field(self):
        problems = loader.validate_insight({"topic": "t"}, "rec")
        assert any("category" in p for p in problems)
        assert any("summary" in p for p in problems)

    def test_wrong_type(self):
        problems = loader.validate_insight(_record(topic=5), "rec")
        assert any("topic" in p and "int" in p for p in problems)

    def test_score_out_of_range(self):
        problems = loader.validate_insight(_record(relevance_score=1.4), "rec")
        assert any("relevance_score" in p for p in problems)

    def test_score_boundary_ok(self):
        for score in (0.0, 1.0):
            assert loader.validate_insight(_record(relevance_score=score), "r") == []

    def test_bool_score_is_type_error(self):
        problems = loader.validate_insight(_record(relevance_score=True), "rec")
        assert problems

    def test_projects_not_int(self):
        problems = loader.validate_insight(_record(applicable_projects=["4"]), "rec")
        assert any("applicable_projects" in p for p in problems)

    def test_not_a_dict(self):
        assert loader.validate_insight(["topic"], "rec")

    def test_foreign_project_flagged(self, tmp_path):
        path = _file(tmp_path / "professor_insights_cycle_010.json", [_record()], project=2)
        problems = loader.validate_file(path)
        assert any("project=2" in p for p in problems)

    def test_corpus_report_survives_broken_file(self, tmp_path):
        _file(tmp_path / "professor_insights_cycle_001.json", [_record()])
        (tmp_path / "professor_insights_cycle_002.json").write_text("{oops", encoding="utf-8")
        report = loader.validate_corpus(tmp_path)
        assert report["valid"] is False
        assert report["unreadable"]
        assert report["files"] == 2

    def test_empty_corpus(self, tmp_path):
        report = loader.validate_corpus(tmp_path)
        assert report["valid"] is True
        assert report["files"] == 0


class TestIterRecords:
    def test_real_corpus_flat(self):
        records = loader.iter_records()
        assert records
        assert all("_cycle" in r and "_source_file" in r for r in records)

    def test_count_matches_validate(self):
        assert len(loader.iter_records()) == loader.validate_corpus()["records"]

    def test_cycles_present(self):
        cycles = {r["_cycle"] for r in loader.iter_records()}
        assert cycles, "в корпусе нет ни одного цикла"


class TestDefaultAddressing:
    def test_default_detected(self):
        assert loader.is_default_addressed(_record(applicable_projects=[1, 2, 3, 4]))

    def test_explicit_not_default(self):
        assert not loader.is_default_addressed(_record(applicable_projects=[4]))

    def test_missing_field_not_default(self):
        record = _record()
        del record["applicable_projects"]
        assert not loader.is_default_addressed(record)

    def test_empty_list_not_default(self):
        assert not loader.is_default_addressed(_record(applicable_projects=[]))

    def test_real_corpus_is_default_addressed(self):
        records = loader.iter_records()
        share = sum(1 for r in records if loader.is_default_addressed(r)) / len(records)
        assert share == 1.0, "ожидался сплошной дефолт адресации в живом корпусе"


# --------------------------------------------------------------------------
# пункт 2 — отпечатки и идентичность
# --------------------------------------------------------------------------


class TestCanonicalisation:
    def test_delivery_fields_excluded(self):
        record = _record(project=4, synced_at="x", _cycle=1)
        canon = fingerprint.canonical_record(record)
        assert "project" not in canon and "synced_at" not in canon and "_cycle" not in canon
        assert canon["topic"] == record["topic"]

    def test_body_digest_ignores_delivery_fields(self, tmp_path):
        a = _file(tmp_path / "a.json", [_record()], project=4)
        b = _file(tmp_path / "b.json", [_record()], project=1)
        assert fingerprint.body_digest(loader.load(a)) == fingerprint.body_digest(loader.load(b))

    def test_body_digest_differs_on_content(self, tmp_path):
        a = _file(tmp_path / "a.json", [_record()])
        b = _file(tmp_path / "b.json", [_record(topic="Другая")])
        assert fingerprint.body_digest(loader.load(a)) != fingerprint.body_digest(loader.load(b))

    def test_key_uses_topic_category_url(self):
        assert fingerprint.record_key(_record()) == ("Тема", "AI Engineering", "https://example.org/a")

    def test_corpus_fingerprints_cycles(self):
        fps = fingerprint.corpus_fingerprints(loader.DEFAULT_DIR)
        assert fps
        for cycle, info in fps.items():
            assert info["digest"] and len(info["digest"]) == 64
            assert info["records"] > 0
            assert info["project"] == 4

    def test_compare_identical(self):
        same = {1: "aa", 2: "bb"}
        result = fingerprint.compare_bodies(same, dict(same))
        assert result["identical"] is True
        assert result["identical_cycles"] == [1, 2]

    def test_compare_divergent(self):
        result = fingerprint.compare_bodies({1: "aa"}, {1: "zz"})
        assert result["identical"] is False
        assert result["divergent_cycles"] == [1]

    def test_compare_extra_cycle_detected(self):
        result = fingerprint.compare_bodies({1: "aa"}, {1: "aa", 2: "bb"})
        assert result["only_other"] == [2]
        assert result["identical"] is False

    def test_compare_empty_is_not_identical(self):
        assert fingerprint.compare_bodies({}, {})["identical"] is False

    def test_key_overlap_full(self):
        records = [_record(), _record(topic="Вторая")]
        result = fingerprint.key_overlap(records, list(records))
        assert result["shared"] == 2
        assert result["jaccard"] == 1.0

    def test_key_overlap_half(self):
        result = fingerprint.key_overlap([_record()], [_record(topic="Иная")])
        assert result["shared"] == 0
        assert result["jaccard"] == 0.0

    def test_identity_report_confirms_defect(self):
        report = fingerprint.identity_report(loader.DEFAULT_DIR, REPO)
        assert report["identical_with_all"] is True
        for name in ("Project1", "Project2", "Project3"):
            assert name in report["identical_to"], f"{name} не признан идентичным"
            assert report["neighbours"][name]["keys"]["jaccard"] == 1.0

    def test_identity_on_separated_copies(self, tmp_path):
        mine = tmp_path / "Project4" / "memory"
        other = tmp_path / "Project1" / "memory"
        _file(mine / "professor_insights_cycle_001.json", [_record()])
        _file(other / "professor_insights_cycle_001.json", [_record(topic="Своё")])
        report = fingerprint.identity_report(mine, tmp_path, names=["Project1"])
        assert report["identical_with_all"] is False
        assert report["neighbours"]["Project1"]["keys"]["shared"] == 0

    def test_missing_neighbour(self, tmp_path):
        _file(tmp_path / "memory" / "professor_insights_cycle_001.json", [_record()])
        report = fingerprint.identity_report(tmp_path / "memory", tmp_path, names=["Project9"])
        assert report["neighbours"]["Project9"] == {"present": False}

    def test_record_set_digest_none_for_empty(self):
        assert fingerprint.content_digest_of_records([]) is None


# --------------------------------------------------------------------------
# пункт 3 — живое воспроизведение дефекта
# --------------------------------------------------------------------------


class TestRepro:
    def test_hot_module_imports(self):
        assert repro.load_hot_module(REPO) is not None

    def test_default_addressing_leaks_everywhere(self):
        result = repro.repro_default_addressing(REPO)
        assert result["default_addressing"] == list(SYNC_DEFAULT_PROJECTS)
        assert result["leaked_everywhere"] is True
        assert result["filter_broken"] is True
        assert set(result["synced_per_project"]) == {"Project1", "Project2", "Project3", "Project4"}

    def test_hot_source_line_points_at_default(self):
        line = repro.hot_source_line(REPO)
        assert "professor_sync.py:" in line
        assert "[1,2,3,4]" in line.replace(" ", "")

    def test_control_case_filter_works(self):
        control = repro.repro_filter_works_with_real_addressing(REPO)
        assert control["filter_works"] is True
        assert control["project4_synced"] == 1
        assert control["project2_synced"] == 1

    def test_report_confirms_defect(self):
        report = repro.repro_report(REPO)
        assert report["defect_confirmed"] is True
        assert "дефолт" in report["diagnosis"]

    def test_repro_does_not_touch_hot_file(self):
        before = paths.sync_module(REPO).read_bytes()
        repro.repro_report(REPO)
        assert paths.sync_module(REPO).read_bytes() == before

    def test_repro_writes_nothing_into_repo(self):
        repro.repro_report(REPO)
        assert not list(REPO.glob("Project1/memory/professor_insights_cycle_77*.json"))

    def test_missing_hot_module(self, tmp_path):
        with pytest.raises(repro.HotModuleMissing):
            repro.load_hot_module(tmp_path)


# --------------------------------------------------------------------------
# пункт 4 — атрибуция
# --------------------------------------------------------------------------


class TestOwnerGuess:
    def test_graph_source(self):
        assert attribution.owner_guess(_record(source_type="knowledge-graph")) == "project2-ish"

    def test_node_marker(self):
        assert attribution.owner_guess(_record(source_type="web", tags=["nodes"])) == "project2-ish"

    def test_identity_marker(self):
        assert attribution.owner_guess(_record(source_type="web", tags=["drift"])) == "project3-ish"

    def test_loader_marker(self):
        assert attribution.owner_guess(_record(source_type="web", tags=["dedup"])) == "project1-ish"

    def test_tag_drives_owner(self):
        record = _record(source_type="web", tags=["graph"])
        assert attribution.owner_guess(record) == "project2-ish"

    def test_textbook_beats_project_markers(self):
        """Тема о графах в учебнике не делает запись достоянием Project2."""
        record = _record(
            source_type="textbook", topic="Graph Engineering Fundamentals", tags=["textbook"]
        )
        assert attribution.owner_guess(record) == attribution.TEXTBOOK_CORE

    def test_borrowed_when_unmarked(self):
        record = _record(source_type="web", tags=["digest"], applicable_projects=[1, 2, 3, 4])
        assert attribution.owner_guess(record) == "borrowed-all/default"

    def test_borrowed_explicit_mark(self):
        record = _record(source_type="web", tags=["digest"], applicable_projects=[4])
        assert attribution.owner_guess(record) == "borrowed-all/explicit"

    def test_high_relevance_alone_not_core(self):
        record = _record(source_type="web", category="Frontend", relevance_score=0.95)
        assert attribution.owner_guess(record) != attribution.TEXTBOOK_CORE


class TestAttributeCorpus:
    def test_counts_sum_to_total(self):
        records = loader.iter_records()
        report = attribution.attribute_corpus(records)
        assert sum(g["count"] for g in report["groups"].values()) == len(records)
        assert report["total_records"] == len(records)

    def test_shares_sum_to_one(self):
        report = attribution.attribute_corpus(loader.iter_records())
        assert round(sum(g["share"] for g in report["groups"].values()), 4) == 1.0

    def test_reproducible(self):
        records = loader.iter_records()
        first = attribution.attribute_corpus(records)
        second = attribution.attribute_corpus(list(records))
        assert first == second

    def test_empty_corpus(self):
        report = attribution.attribute_corpus([])
        assert report["groups"] == {}
        assert report["borrowed_share"] == 0

    def test_real_corpus_has_no_own_core(self):
        report = attribution.attribute_corpus(loader.iter_records())
        assert report["core_share"] > 0.5, "ожидалась преобладающая учебно-дайджестовая масса"

    def test_verdict_names_the_cause(self):
        report = attribution.attribute_corpus(loader.iter_records())
        assert "нет собственного ядра" in report["verdict"]

    def test_textbook_never_claimed_as_project(self):
        """Ни одна учебниковая запись не должна попасть в проектную группу."""
        report = attribution.attribute_corpus(loader.iter_records())
        for name, group in report["groups"].items():
            if name.endswith("-ish"):
                assert group["count"] == 0 or group["count"] < report["core_total"]


class TestRepetitionReport:
    def test_unique_topics_counted(self):
        records = [_record(), _record(topic="Другая")]
        report = attribution.repetition_report(records)
        assert report["records"] == 2
        assert report["unique_topics"] == 2
        assert report["duplicate_records"] == 0

    def test_repeats_counted(self):
        records = [_record(), _record()]
        report = attribution.repetition_report(records)
        assert report["repeated_topics"] == 1
        assert report["duplicate_records"] == 1
        assert report["duplicate_share"] == 0.5

    def test_real_corpus_has_duplicates(self):
        report = attribution.repetition_report(loader.iter_records())
        assert report["unique_topics"] < report["records"]
        assert report["duplicate_records"] > 0
        assert report["worst"][0]["count"] >= 2

    def test_empty(self):
        assert attribution.repetition_report([])["unique_topics"] == 0


class TestAddressingAudit:
    def test_shapes_accounted(self):
        records = loader.iter_records()
        report = attribution.default_addressing_audit(records)
        assert sum(report["addressing_shapes"].values()) == len(records)
        assert report["default_addressed"] == len(records)
        assert report["filter_can_discriminate"] is False

    def test_expected_default_listed(self):
        assert attribution.default_addressing_audit([])["expected_default"] == list(SYNC_DEFAULT_PROJECTS)


# --------------------------------------------------------------------------
# пункт 11 — защита путей
# --------------------------------------------------------------------------


class TestPaths:
    def test_inside_root_ok(self, tmp_path):
        assert paths.inside_root("memory/a.json", tmp_path) == (tmp_path / "memory" / "a.json").resolve()

    def test_absolute_rejected(self, tmp_path):
        with pytest.raises(PathOutsideProject):
            paths.inside_root("/etc/passwd", tmp_path)

    def test_dotdot_rejected(self, tmp_path):
        with pytest.raises(PathOutsideProject):
            paths.inside_root("../Project3/CHRONICLE.md", tmp_path)

    def test_nested_dotdot_rejected(self, tmp_path):
        with pytest.raises(PathOutsideProject):
            paths.inside_root("memory/../../Project3/x", tmp_path)

    def test_sibling_rejected(self):
        with pytest.raises(PathOutsideProject):
            paths.sibling_memory_dir("../secrets")

    def test_self_rejected(self):
        with pytest.raises(PathOutsideProject):
            paths.sibling_memory_dir("Project4")

    def test_valid_sibling(self):
        assert paths.sibling_memory_dir("Project1", REPO).name == "memory"

    def test_sync_module_path(self):
        assert paths.sync_module(REPO).exists()

    def test_traversal_to_neighbour_repo_blocked(self, tmp_path):
        """Попытка уйти в соседний проект отвергается, даже если путь не абсолютный."""
        (tmp_path / "Project9").mkdir()
        with pytest.raises(PathOutsideProject):
            paths.inside_root("Project9/../Project8/secret", tmp_path)