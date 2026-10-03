"""Тесты безопасной записи в CHRONICLE.md (пункт 12 плана) и сквозные проверки."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p4_provenance import (  # noqa: E402
    canon,
    chronicle,
    fingerprint,
    loader,
    paths,
)

REPO = Path(__file__).resolve().parent.parent.parent


class TestChronicle:
    def test_creates_file(self, tmp_path):
        target = chronicle.append_slot("Тело блока", "Проверка", root=tmp_path)
        text = target.read_text(encoding="utf-8")
        assert "## Слот" in text
        assert "Проверка" in text
        assert "Тело блока" in text

    def test_appends_to_existing(self, tmp_path):
        (tmp_path / "CHRONICLE.md").write_text("# Проект 4 Chronicle\n\nстарый текст\n", encoding="utf-8")
        target = chronicle.append_slot("Новое", "Проверка", root=tmp_path)
        text = target.read_text(encoding="utf-8")
        assert "старый текст" in text
        assert "Новое" in text

    def test_backup_created(self, tmp_path):
        (tmp_path / "CHRONICLE.md").write_text("старое\n", encoding="utf-8")
        chronicle.append_slot("Новое", "Проверка", root=tmp_path)
        backup = tmp_path / "CHRONICLE.md.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "старое\n"

    def test_no_duplicate_heading(self, tmp_path):
        chronicle.append_slot("Первый", "Проверка", when="2026-01-01 00:00", root=tmp_path)
        with pytest.raises(chronicle.ChronicleError):
            chronicle.append_slot("Второй", "Проверка", when="2026-01-01 00:00", root=tmp_path)
        text = (tmp_path / "CHRONICLE.md").read_text(encoding="utf-8")
        assert text.count("## Слот 2026-01-01 00:00 — Проверка") == 1
        assert "Второй" not in text

    def test_safe_variant_swallows_duplicate(self, tmp_path):
        chronicle.append_slot_safe("Первый", "Проверка", when="2026-01-01 00:00", root=tmp_path)
        result = chronicle.append_slot_safe("Второй", "Проверка", when="2026-01-01 00:00", root=tmp_path)
        assert result is None

    def test_different_when_is_new_block(self, tmp_path):
        chronicle.append_slot("A", "Проверка", when="2026-01-01 00:00", root=tmp_path)
        chronicle.append_slot("B", "Проверка", when="2026-01-02 00:00", root=tmp_path)
        text = (tmp_path / "CHRONICLE.md").read_text(encoding="utf-8")
        assert text.count("## Слот") == 2

    def test_no_temp_files_left(self, tmp_path):
        chronicle.append_slot("Тело", "Проверка", root=tmp_path)
        leftovers = [p.name for p in tmp_path.glob(".chronicle-*")]
        assert leftovers == []

    def test_refuses_outside_root(self, tmp_path):
        with pytest.raises(paths.PathOutsideProject):
            chronicle.append_slot("Тело", "Проверка", chronicle="../Project3/CHRONICLE.md", root=tmp_path)

    def test_refuses_absolute(self, tmp_path):
        with pytest.raises(paths.PathOutsideProject):
            chronicle.append_slot("Тело", "Проверка", chronicle="/tmp/evil-chronicle.md", root=tmp_path)

    def test_existing_without_trailing_newline(self, tmp_path):
        (tmp_path / "CHRONICLE.md").write_text("без перевода строки", encoding="utf-8")
        target = chronicle.append_slot("Новое", "Проверка", root=tmp_path)
        text = target.read_text(encoding="utf-8")
        assert "без перевода строки\n\n## Слот" in text

    def test_has_slot_detection(self):
        assert chronicle.has_slot("## Слот 2026-01-01 00:00 — X\n", "## Слот 2026-01-01 00:00 — X")
        assert not chronicle.has_slot("текст", "## Слот 2026-01-01 00:00 — X")

    def test_heading_format(self):
        assert chronicle.slot_heading("X", "2026-01-01 00:00") == "## Слот 2026-01-01 00:00 — X"


# --------------------------------------------------------------------------
# сквозные проверки: пакет целиком на живом дереве
# --------------------------------------------------------------------------


class TestLiveTree:
    def test_canonical_json_roundtrip(self):
        """Канонический корпус записывается и читается обратно без потерь счёта."""
        records = loader.iter_records()
        canonical = canon.canonicalise(records)
        path = paths.PROJECT_DIR / "artifacts" / "test_canon.json"
        try:
            canon.write_canonical_json(canonical, "artifacts/test_canon.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["records_in"] == len(records)
            assert len(data["records"]) == canonical["canonical_out"]
            assert sum(r["occurrences"] for r in data["records"]) == len(records)
        finally:
            path.unlink(missing_ok=True)

    def test_report_matches_recomputed_numbers(self):
        """Отчёт не должен разойтись с пересчётом (пункт 9)."""
        from p4_provenance import report

        text = report.render_report(loader.DEFAULT_DIR, REPO)
        facts = report.report_facts(loader.DEFAULT_DIR, REPO)
        records = loader.iter_records()
        assert f"| Записей всего | {len(records)} |" in text
        assert facts["records"] == len(records)
        assert facts["cycles"] == len(fingerprint.corpus_fingerprints(loader.DEFAULT_DIR))

    def test_corpus_numbers_agree_across_modules(self):
        """Один и тот же корпус — одни и те же числа во всех модулях."""
        from p4_provenance import attribution, canary, metrics

        records = loader.iter_records()
        validation = loader.validate_corpus()
        assert validation["records"] == len(records)
        assert metrics.metrics(records)["records"] == len(records)
        assert canary.canary(loader.DEFAULT_DIR, REPO)["records"] == len(records)
        assert attribution.repetition_report(records)["records"] == len(records)

    def test_canonical_out_never_exceeds_in(self):
        canonical = canon.canonicalise(loader.iter_records())
        assert canonical["canonical_out"] <= canonical["records_in"]

    def test_modules_do_not_import_each_other_in_a_cycle(self):
        """`report` тянет всё; нижние модули не должны знать про `report`."""
        import p4_provenance.attribution as attribution
        import p4_provenance.canon as canon_mod
        import p4_provenance.canary as canary_mod
        import p4_provenance.loader as loader_mod

        for module in (loader_mod, canon_mod, attribution):
            source = Path(module.__file__).read_text(encoding="utf-8")
            assert "import report" not in source
        assert "from .report" not in Path(canary_mod.__file__).read_text(encoding="utf-8")

    def test_hot_file_untouched_after_full_run(self):
        """Полный прогон пакета не меняет горячий файл (включая canary/repro)."""
        from p4_provenance import repro

        before = paths.sync_module(REPO).read_bytes()
        repro.repro_report(REPO)
        assert paths.sync_module(REPO).read_bytes() == before