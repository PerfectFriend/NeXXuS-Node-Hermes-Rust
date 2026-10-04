"""Тесты пункта 13: машиночитаемые факты для `tools/cycle_claim_gate.py`.

Заявка Искателя проверяется так: собранные из реальных артефактов `facts`
проходят настоящий гейт при честном заявлении (код 0) и роняют его при
завышенном (код 2). Копия гейта не используется — импортируется живой файл.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from p4_provenance import gate, paths  # noqa: E402

sys.path.insert(0, str(paths.REPO_DIR))


# --------------------------------------------------------------------------
# вспомогательное
# --------------------------------------------------------------------------


def _subproject(tmp_path: Path) -> Path:
    """Временный проект с двумя зелёными тестами и реестром дефектов."""
    root = tmp_path / "sub"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_ok.py").write_text(
        textwrap.dedent(
            """
            def test_one():
                assert 1 + 1 == 2

            def test_two():
                assert "a" in "abc"
            """
        ),
        encoding="utf-8",
    )
    (root / "defect_registry.json").write_text(
        json.dumps(
            {
                "defects": [
                    {"id": "D1", "status": "closed"},
                    {"id": "D2", "status": "closed"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def _honest_claim(facts: dict) -> dict:
    run = facts["test_run"]
    reg = facts["defect_registry"] or {}
    return {
        "tests_total": run.get("collected"),
        "tests_passed": run.get("passed"),
        "defects_closed": reg.get("closed"),
        "cycle_closed": False,
    }


# --------------------------------------------------------------------------
# поиск рабочего pytest
# --------------------------------------------------------------------------


def test_resolve_pytest_finds_working_runner():
    pytest_cmd = gate.resolve_pytest(PROJECT)
    assert pytest_cmd, "на этой машине pytest обязан находиться (~/build/bin/pytest)"
    code, out = gate._run(pytest_cmd + ["--version"], timeout=60)
    assert code == 0, out


def test_candidate_pytests_prefers_interpreter_not_bare_script():
    """Кандидат из шебанга полезнее голого `pytest`: тот может быть без pytest."""
    cands = gate.candidate_pytests(PROJECT)
    assert cands, "кандидаты pytest не должны быть пустым списком"
    assert any(c[0].endswith("python") or c[0].endswith("python3") for c in cands), cands


# --------------------------------------------------------------------------
# разбор junit-xml
# --------------------------------------------------------------------------


def test_read_junit_parses_machine_report(tmp_path):
    xml = tmp_path / "report.xml"
    xml.write_text(
        '<testsuites><testsuite name="pytest" tests="7" failures="2" errors="1" '
        'skipped="1"></testsuite></testsuites>',
        encoding="utf-8",
    )
    facts = gate.read_junit(xml)
    assert facts["collected"] == 7
    assert facts["failed"] == 3
    assert facts["skipped"] == 1
    assert facts["passed"] == 3


def test_read_junit_reports_error_instead_of_zeros(tmp_path):
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuite><oops", encoding="utf-8")
    facts = gate.read_junit(broken)
    assert "error" in facts, facts
    assert "passed" not in facts, "битый отчёт не должен читаться как «0 тестов»"


def test_read_junit_without_testsuite_is_error(tmp_path):
    xml = tmp_path / "empty.xml"
    xml.write_text("<other/>", encoding="utf-8")
    assert "error" in gate.read_junit(xml)


# --------------------------------------------------------------------------
# реальный прогон
# --------------------------------------------------------------------------


def test_run_tests_reports_real_counts(tmp_path):
    root = _subproject(tmp_path)
    facts = gate.run_tests(root, target="tests")
    assert "error" not in facts, facts
    assert facts["collected"] == 2, facts
    assert facts["passed"] == 2, facts
    assert facts["failed"] == 0, facts


def test_run_tests_fails_loudly_when_pytest_missing(tmp_path, monkeypatch):
    """Нет рабочего pytest — это ошибка, а не «0 тестов»."""
    monkeypatch.setattr(gate, "candidate_pytests", lambda project: [])
    facts = gate.run_tests(_subproject(tmp_path), target="tests")
    assert facts.get("error"), facts
    assert "не найден" in facts["error"] or "НЕ выполнен" in facts["error"], facts


def test_run_tests_reports_error_when_nothing_collected(tmp_path):
    root = tmp_path / "empty_project"
    (root / "tests").mkdir(parents=True)
    facts = gate.run_tests(root, target="tests")
    assert facts.get("error") or facts["collected"] == 0, facts
    if "error" not in facts:
        # pytest без тестов обязан быть виден как 0 собрано, а не как «2 зелёных»
        assert facts["passed"] == 0, facts


def test_run_tests_missing_project_dir_is_error():
    facts = gate.run_tests("/home/thomas/LivingCode/Project4/нет-такого-каталога")
    assert "error" in facts, facts


# --------------------------------------------------------------------------
# реестр дефектов
# --------------------------------------------------------------------------


def test_read_registry_counts_statuses(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    (root / "defect_registry.json").write_text(
        json.dumps({"defects": [{"status": "open"}, {"status": "closed"},
                                {"status": "closed"}, {"status": "wip"}]}),
        encoding="utf-8",
    )
    reg = gate.read_registry(root)
    assert (reg["open"], reg["closed"], reg["total"]) == (2, 2, 4), reg


def test_read_registry_missing_file_is_none(tmp_path):
    assert gate.read_registry(tmp_path) is None, "нет файла — это None, а не нули"


def test_read_registry_broken_json_is_error(tmp_path):
    (tmp_path / "defect_registry.json").write_text("{не json", encoding="utf-8")
    reg = gate.read_registry(tmp_path)
    assert reg and "error" in reg, reg


def test_read_registry_accepts_flat_counters(tmp_path):
    (tmp_path / "defect_registry.json").write_text(
        json.dumps({"open": 1, "closed": 4, "total": 5}), encoding="utf-8")
    reg = gate.read_registry(tmp_path)
    assert (reg["open"], reg["closed"], reg["total"]) == (1, 4, 5), reg


def test_registry_by_status_sums_match_read_registry(tmp_path):
    root = _subproject(tmp_path)
    reg = gate.read_registry(root)
    counts = gate.registry_by_status(root)
    assert sum(counts.values()) == reg["total"], (counts, reg)
    assert counts.get("open", 0) == reg["open"], (counts, reg)


# --------------------------------------------------------------------------
# сборка facts и сверка с настоящим гейтом
# --------------------------------------------------------------------------


def test_load_gate_is_live_file_not_a_copy():
    module = gate.load_gate()
    assert Path(module.__file__).resolve() == paths.REPO_DIR.joinpath(*gate.GATE_REL), \
        module.__file__
    assert hasattr(module, "check")


def test_facts_from_real_run_pass_honest_claim_through_real_gate(tmp_path):
    """Пункт 13: честное заявление подтверждается гейтом (код 0)."""
    root = _subproject(tmp_path)
    facts = gate.build_facts(root, target="tests")
    claim = _honest_claim(facts)
    assert gate.gate_exit(facts, claim, paths.REPO_DIR) == 0, gate.gate_check(facts, claim)


def test_inflated_claim_is_rejected_by_real_gate(tmp_path):
    """Пункт 13: завышенное «всё зелёное» роняет гейт (код 2)."""
    root = _subproject(tmp_path)
    facts = gate.build_facts(root, target="tests")
    claim = _honest_claim(facts)
    claim["tests_passed"] = (facts["test_run"]["passed"] or 0) + 5
    claim["tests_total"] = (facts["test_run"]["collected"] or 0) + 5
    claim["cycle_closed"] = True
    problems = gate.gate_check(facts, claim, paths.REPO_DIR)
    assert problems, "завышенное заявление обязано быть отклонено"
    assert gate.gate_exit(facts, claim, paths.REPO_DIR) == 2


def test_absent_test_run_cannot_confirm_green_claim(tmp_path):
    """--no-run: заявление о зелёных тестах нечем подтвердить."""
    facts = gate.build_facts(_subproject(tmp_path), run=False)
    assert "error" in facts["test_run"], facts
    problems = gate.gate_check(facts, {"tests_passed": 0, "cycle_closed": True},
                              paths.REPO_DIR)
    assert problems, "отсутствие прогона обязано ронять гейт"


def test_missing_registry_blocks_claim(tmp_path):
    root = tmp_path / "no_registry"
    (root / "tests").mkdir(parents=True)
    facts = gate.build_facts(root, junit=None, run=False)
    assert facts["defect_registry"] is None, facts
    problems = gate.gate_check(facts, {"defects_closed": 3}, paths.REPO_DIR)
    assert any("реестр" in p for p in problems), problems


def test_write_case_is_confined_to_project_root(tmp_path):
    """Пункт 11: запись вне проекта запрещена (проверяется на пункте 13)."""
    outside = tmp_path / "куда-то-не-туда.json"
    with pytest.raises(Exception):
        gate.write_case(outside, gate.claim_case("x", {}, {}))
    assert not outside.exists()


def test_write_case_writes_valid_json_inside_project(tmp_path):
    root = paths.PROJECT_DIR
    rel = "state/cases/тест-кейс.json"
    path = gate.write_case(rel, gate.claim_case("честный", {"tests_passed": 1}, {}))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["name"] == "честный"
        assert path.is_relative_to(root.resolve())
    finally:
        path.unlink(missing_ok=True)


def test_claim_case_and_digest_shapes():
    case = gate.claim_case("кейс", {"tests_passed": 2}, {
        "test_run": {"passed": 2, "failed": 0, "collected": 2},
        "defect_registry": {"open": 0, "closed": 1, "total": 1},
    })
    assert set(case) == {"name", "claim", "facts"}
    digest = gate.facts_digest(case["facts"])
    assert "passed=2" in digest and "open=0" in digest, digest


def test_digest_marks_absent_run_and_registry():
    digest = gate.facts_digest({"test_run": {"error": "нет"}, "defect_registry": None})
    assert "НЕ ВЫПОЛНЕН" in digest and "нет" in digest, digest


def test_gate_accepts_json_file_as_entrypoint(tmp_path):
    """Файл, который пишет CLI, читается настоящим гейтом как входной."""
    root = _subproject(tmp_path)
    facts = gate.build_facts(root, target="tests")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([
        gate.claim_case("честный", _honest_claim(facts), facts),
        gate.claim_case("завышенный",
                        {**_honest_claim(facts), "tests_passed": 999}, facts),
    ], ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(paths.REPO_DIR / "tools" / "cycle_claim_gate.py"), str(path)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ПРОВАЛ завышенный" in proc.stdout, proc.stdout
    assert "ПОДТВЕРЖДЕНО честный" in proc.stdout, proc.stdout


# --------------------------------------------------------------------------
# пункт 14: CLI-команда `gate`
# --------------------------------------------------------------------------


def _cli(args, project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "p4_provenance", "-r", str(paths.REPO_DIR), "gate",
         "--project", str(project), *args],
        capture_output=True, text=True, timeout=900, cwd=str(PROJECT),
    )


def test_cli_gate_prints_ready_json_accepted_by_real_gate(tmp_path):
    """Вывод CLI без `--claim` — входной файл настоящего гейта (код 0)."""
    root = _subproject(tmp_path)
    proc = _cli(["--target", "tests", "--name", "честный"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    case = json.loads(proc.stdout)
    assert set(case) == {"name", "claim", "facts"}, case
    assert case["facts"]["test_run"]["failed"] == 0, case["facts"]
    path = tmp_path / "cli_case.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    gate_proc = subprocess.run(
        [sys.executable, str(paths.REPO_DIR / "tools" / "cycle_claim_gate.py"), str(path)],
        capture_output=True, text=True, timeout=120,
    )
    assert gate_proc.returncode == 0, gate_proc.stdout + gate_proc.stderr


def test_cli_gate_returns_0_on_honest_claim_and_2_on_inflated(tmp_path):
    root = _subproject(tmp_path)
    facts = gate.build_facts(root, target="tests")
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_honest_claim(facts), ensure_ascii=False), encoding="utf-8")
    ok_proc = _cli(["--target", "tests", "--claim", str(good)], root)
    assert ok_proc.returncode == 0, ok_proc.stdout + ok_proc.stderr
    assert json.loads(ok_proc.stdout)["подтверждено"] is True

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**_honest_claim(facts), "tests_passed": 999},
                              ensure_ascii=False), encoding="utf-8")
    bad_proc = _cli(["--target", "tests", "--claim", str(bad)], root)
    assert bad_proc.returncode == 2, bad_proc.stdout + bad_proc.stderr
    assert json.loads(bad_proc.stdout)["расхождения"], bad_proc.stdout


def test_cli_gate_rejects_claim_when_run_was_not_performed(tmp_path):
    """`--no-run` и завышенное «всё зелёное» → код 2, а не подтверждение."""
    root = _subproject(tmp_path)
    claim = tmp_path / "claim.json"
    claim.write_text(json.dumps({"tests_passed": 500, "tests_total": 500,
                                 "defects_closed": 0, "cycle_closed": True},
                                ensure_ascii=False), encoding="utf-8")
    proc = _cli(["--no-run", "--claim", str(claim)], root)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    problems = json.loads(proc.stdout)["расхождения"]
    assert any("НЕ ВЫПОЛНЕН" in p or "прогон" in p for p in problems), problems


def _cli_with_stdin(project: Path, claim: Dict[str, Any]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "p4_provenance", "-r", str(paths.REPO_DIR), "gate",
         "--project", str(project), "--target", "tests", "--claim", "-",
         "--save", "cases/cli_case.json"],
        input=json.dumps(claim, ensure_ascii=False),
        capture_output=True, text=True, timeout=900, cwd=str(PROJECT),
    )


def test_cli_gate_stdin_claim_and_save_stay_inside_project(tmp_path):
    proc = _cli_with_stdin(tmp_path / "нет-такого",
                           {"tests_passed": 10, "cycle_closed": True})
    # каталога проекта нет → факты не собраны → код 2, а не «подтверждено»
    assert proc.returncode == 2, proc.stdout + proc.stderr

    root = _subproject(tmp_path)
    facts = gate.build_facts(root, target="tests")
    proc = subprocess.run(
        [sys.executable, "-m", "p4_provenance", "-r", str(paths.REPO_DIR), "gate",
         "--project", str(root), "--target", "tests", "--claim", "-",
         "--save", "cases/cli_case.json"],
        input=json.dumps(_honest_claim(facts), ensure_ascii=False),
        capture_output=True, text=True, timeout=900, cwd=str(PROJECT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "кейс записан" in proc.stderr, proc.stderr
    saved = PROJECT / "cases" / "cli_case.json"
    assert saved.exists(), "кейс должен лежать внутри Project4"
    assert json.loads(saved.read_text(encoding="utf-8"))["facts"]["test_run"]["failed"] == 0


def test_cli_gate_reports_unreadable_claim(tmp_path):
    root = _subproject(tmp_path)
    bad = tmp_path / "не-json.json"
    bad.write_text("{это не json", encoding="utf-8")
    proc = _cli(["--target", "tests", "--claim", str(bad)], root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "не прочитано" in proc.stderr, proc.stderr


# --------------------------------------------------------------------------
# отсутствие регрессии по живому гейту
# --------------------------------------------------------------------------


def test_gate_tolerates_zero_tolerance_contract():
    module = gate.load_gate()
    assert module.TOLERANCE == 0, "гейт по-прежнему не прощает расхождений"