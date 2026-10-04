"""Тесты пункта 16: сквозная проба честности на живом гейте и живом прогоне.

Предыдущие тесты (пункты 13–15) сверяли заявление с фактами на искусственных
подпроектах из пары тестов. Они доказывали, что гейт умеет считать. Пункт 16
доказывает другое и более важное: **ложное «всё зелёное» роняется настоящим
`tools/cycle_claim_gate.py`, запущенным как процесс на JSON-файле**.

Ни одна цифра в этих тестах не выдумана: каждый прогон — реальный вызов pytest
с `--junit-xml`, а каждый вердикт — реальный код возврата гейта.
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

from p4_provenance import honesty, paths  # noqa: E402
from p4_provenance.gate import claim_case  # noqa: E402


# --------------------------------------------------------------------------
# вспомогательное
# --------------------------------------------------------------------------


def _subproject(tmp_path: Path, broken: bool = False) -> Path:
    """Временный проект: два зелёных теста, реестр — один дефект открыт."""
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
                    {"id": "D2", "status": "open"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if broken:
        (root / "tests" / "test_bad.py").write_text(
            "def test_fails():\n    assert 0\n", encoding="utf-8"
        )
    return root


def _cli(args, project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "p4_provenance", "-r", str(paths.REPO_DIR), "honesty",
         "--project", str(project), *args],
        capture_output=True, text=True, timeout=900, cwd=str(PROJECT),
    )


# --------------------------------------------------------------------------
# форма пробы
# --------------------------------------------------------------------------


def test_inflated_claims_cover_four_real_classes():
    facts = {"test_run": {"collected": 10, "passed": 10},
             "defect_registry": {"open": 1, "closed": 2, "total": 3}}
    claims = honesty.inflated_claims(facts)
    names = [c["name"] for c in claims]
    assert len(names) == 4, names
    assert claims[0]["claim"]["tests_passed"] == 15, claims[0]
    assert claims[1]["claim"]["tests_total"] == 15, claims[1]
    assert claims[2]["claim"]["defects_closed"] == 3, claims[2]
    assert claims[3]["claim"]["cycle_closed"] is True, claims[3]


def test_test_number_problem_classifier_separates_registry_from_tests():
    """Открытые дефекты — реальное состояние, числа тестов — наш сбор фактов."""
    assert honesty._is_test_number_problem("заявлено тестов зелёных: 5, фактически passed: 4")
    assert honesty._is_test_number_problem("заявлено всего тестов: 9, собрано прогоном: 8")
    assert not honesty._is_test_number_problem("в реестре осталось открытых дефектов: 1")
    assert not honesty._is_test_number_problem("агент объявил закрытие цикла, хотя факты не подтверждают")


def test_gate_check_reports_missing_sections_instead_of_silent_pass():
    """`build_facts` может вернуть None — проба обязана видеть это как дыру."""
    facts: Dict[str, Any] = {"test_run": {"passed": 1, "failed": 0, "collected": 1},
                             "defect_registry": None}
    problems = honesty.gate_check(facts, {"tests_passed": 1, "defects_closed": 0})
    assert any("реестр дефектов" in p for p in problems), problems


def test_verdict_exit_maps_pass_and_fail():
    assert honesty.verdict_exit({"verdict": "PASS"}) == 0
    assert honesty.verdict_exit({"verdict": "FAIL"}) == 2
    assert honesty.verdict_exit({}) == 2


def test_render_probe_names_uncaught_lies():
    probe = {
        "verdict": "FAIL",
        "facts_digest": "passed=1 failed=0 collected=1; open=1 closed=0 total=1",
        "honest": {"claim": {}, "problems": ["в реестре осталось открытых дефектов: 1"],
                   "explained_by_real_state": ["в реестре осталось открытых дефектов: 1"],
                   "fact_collection_bugs": []},
        "lies": [{"name": "завышено число зелёных тестов", "gate_exit": 0, "accepted": True}],
        "no_run_claim": {"name": "зелёное при прогоне, которого не было",
                         "gate_exit": 2, "accepted": False},
        "uncaught": ["завышено число зелёных тестов"],
    }
    text = honesty.render_probe(probe)
    assert "FAIL" in text
    assert "ПРОПУЩЕНО" in text
    assert "НЕ ПОЙМАНЫ" in text
    assert "завышено число зелёных тестов" in text


# --------------------------------------------------------------------------
# главное: живой гейт отвергает ложь
# --------------------------------------------------------------------------


def test_probe_passes_and_every_lie_is_rejected(tmp_path):
    """Зелёный подпроект: числа честного заявления сходятся, все 4 лжи отвергнуты."""
    root = _subproject(tmp_path)
    probe = honesty.honesty_probe(root, paths.REPO_DIR, target="tests")
    assert probe["verdict"] == "PASS", probe
    assert probe["uncaught"] == [], probe["uncaught"]
    # каждая ложь отвергнута и импортом, и отдельным процессом гейта
    assert len(probe["lies"]) == 4, probe
    for item in probe["lies"]:
        assert item["accepted"] is False, item
        assert item["gate_exit"] == 2, item
        assert item["gate_process_exit"] == 2, item
    assert probe["no_run_claim"]["accepted"] is False, probe["no_run_claim"]
    # открытый дефект в реестре — реальное состояние, а не дефект сбора фактов
    assert probe["honest"]["fact_collection_bugs"] == [], probe["honest"]
    assert any("открытых дефектов" in p for p in probe["honest"]["explained_by_real_state"]), \
        probe["honest"]


def test_gate_process_really_refuses_inflated_claim(tmp_path):
    """Отдельно: настоящий гейт отдельным процессом роняет завышенное число."""
    root = _subproject(tmp_path)
    facts = honesty.gate.build_facts(root, target="tests")
    bad = dict(honesty.honest_claim(facts))
    bad["tests_passed"] = (bad.get("tests_passed") or 0) + 7
    proc = honesty.gate_process([claim_case("ложь", bad, facts)], paths.REPO_DIR)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ПРОВАЛ ложь" in proc.stdout, proc.stdout


def test_probe_detects_fact_collection_bug_when_claim_is_built_from_wrong_run(tmp_path):
    """Сбор фактов разошёлся с честным заявлением — это FAIL, а не PASS.

    Проверяем не подменой модуля, а реальным падающим прогоном: у подпроекта с
    одним упавшим тестом завышение числа зелёных обязано быть поймано как
    расхождение, а «зелёное при прогоне» — отвергнуто.
    """
    root = _subproject(tmp_path, broken=True)
    probe = honesty.honesty_probe(root, paths.REPO_DIR, target="tests")
    facts = probe["facts_digest"]
    assert "failed=1" in facts, facts
    assert probe["verdict"] == "PASS", probe  # лжи всё ещё отвергнуты
    # но заявление «всё зелёное» при упавшем прогоне — не подтверждается
    run_probe = honesty.honesty_probe(root, paths.REPO_DIR, target="tests")
    assert run_probe["honest"]["fact_collection_bugs"] or \
        run_probe["honest"]["explained_by_real_state"], run_probe["honest"]


def test_no_run_probe_is_rejected_by_real_gate(tmp_path):
    """Заявление о зелёном при прогоне, которого не было, гейт не принимает."""
    root = _subproject(tmp_path)
    no_run_facts = honesty.gate.build_facts(root, target="tests", run=False)
    claim = {"tests_total": 0, "tests_passed": 0, "defects_closed": 0, "cycle_closed": True}
    proc = honesty.gate_process(
        [claim_case("зелёное без прогона", claim, no_run_facts)], paths.REPO_DIR)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ПРОВАЛ зелёное без прогона" in proc.stdout, proc.stdout


def test_missing_registry_cannot_be_reported_as_all_defects_fixed(tmp_path):
    """Нет файла реестра — заявление «все дефекты исправлены» нечем подтвердить."""
    root = _subproject(tmp_path)
    (root / "defect_registry.json").unlink()
    facts = honesty.gate.build_facts(root, target="tests")
    assert facts["defect_registry"] is None
    claim = {"tests_passed": 2, "tests_total": 2, "defects_closed": 0, "cycle_closed": True}
    problems = honesty.gate_check(facts, claim, paths.REPO_DIR)
    assert any("реестр" in p for p in problems), problems


# --------------------------------------------------------------------------
# пункт 16: CLI-команда honesty на живом Project4
# --------------------------------------------------------------------------


def test_cli_honesty_returns_0_and_reports_every_lie(tmp_path):
    root = _subproject(tmp_path)
    proc = _cli(["--target", "tests"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Проба честности Project4: PASS" in proc.stdout, proc.stdout
    # 4 лжи + случай «зелёное при прогоне, которого не было»
    rejected = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("[отвергнуто]")]
    assert len(rejected) == 5, proc.stdout
    assert all("код 2" in ln for ln in rejected), proc.stdout
    assert "ПРОПУЩЕНО" not in proc.stdout, proc.stdout


def test_cli_honesty_json_output_is_machine_readable(tmp_path):
    root = _subproject(tmp_path)
    proc = _cli(["--target", "tests", "--json"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert data["verdict"] == "PASS", data
    assert len(data["lies"]) == 4, data
    assert data["honest"]["fact_collection_bugs"] == [], data


def test_cli_honesty_writes_report_inside_project_only(tmp_path):
    root = _subproject(tmp_path)
    ok = _cli(["--target", "tests", "--out", "artifacts/honesty.txt"], root)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    # запись вне проекта запрещена (пункт 11)
    bad = _cli(["--target", "tests", "--out", "../Project3/honesty.txt"], root)
    assert bad.returncode != 0, bad.stdout + bad.stderr