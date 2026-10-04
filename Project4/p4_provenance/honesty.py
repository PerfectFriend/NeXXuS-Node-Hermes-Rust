"""Сквозная проверка честности заявлений (пункт 16 плана, Фаза 2).

Что проверяется. Пункты 13–15 дали машиночитаемые факты и сверку отдельного
заявления. Но оставалась дыра целиком: **ложное «всё зелёное» нигде не было
проверено на настоящем прогоне Project4**. Все предыдущие тесты сверяли
искусственные подпроекты из двух тестов — то есть доказывали, что гейт умеет
считать, но не доказывали, что он роняет реальное ложное заявление живого
проекта. Этот модудль закрывает именно эту дыру.

Модуль делает три вещи и только их:

1. **Берёт настоящий прогон тестов Project4** (`gate.build_facts`) — не
   рукописные числа, а реальный `pytest --junit-xml`.
2. **Прогоняет настоящий гейт** `tools/cycle_claim_gate.py` как отдельный
   процесс на JSON-файле — тем же входом, каким пользуется протокол. Не
   импорт копии и не подмена `check()`.
3. **Доказывает, что ложь роняется**: набор завышенных заявлений, характерных
   для LLM-агента, должен дать код 2 КАЖДЫЙ. Если хоть одно прошло — это
   дефект инструмента, и модуль возвращает провал.

Ключевая тонкость, которую нельзя спрятать. У Project4 есть ОТКРЫТЫЙ дефект
(дефект адресации в горячем `scripts/professor_sync.py`, отдан владельцу). Настоящий
гейт имеет правило «любой открытый дефект — расхождение». Значит **честное**
заявление Project4 тоже получает код 2 — и это правильно: закрывать цикл нельзя.
Поэтому модуль не требует кода 0 от честного заявления. Вместо этого он
проверяет более сильное и более честное свойство:

    все расхождения честного заявления объясняются РЕАЛЬНЫМ состоянием
    (открытые дефекты), и ни одно из них не касается чисел прогона тестов.

Расхождение про числа тестов в честном заявлении означало бы дефект сбора
фактов — вот это уже ненулевой код возврата и провал. Расхождение про
открытые дефекты — не провал, а признак, что гейт работает.

Ничего не выдумывается: все числа в отчёте взяты из тех же словарей, которые
потом предъявляются гейту.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import gate
from .gate import GATE_REL, facts_digest
from .paths import PROJECT_DIR, REPO_DIR, inside_root

#: Подстроки, из-за которых расхождение считаем объяснённым реальным
#: состоянием проекта, а не дефектом сбора фактов.
BENIGN_MARKERS = (
    "открытых дефектов",
    "заявлено закрытых дефектов",
    "закрытие цикла",
)


def _is_test_number_problem(problem: str) -> bool:
    """Расхождение касается ЧИСЕЛ прогона тестов (а не реестра/цикла)."""
    if any(marker in problem for marker in BENIGN_MARKERS):
        return False
    return "тест" in problem


def gate_process(cases: List[Dict[str, Any]],
                 repo: os.PathLike | str = REPO_DIR) -> subprocess.CompletedProcess:
    """Запустить НАСТОЯЩИЙ гейт отдельным процессом на файле с кейсами.

    Отдельный процесс, а не `load_gate().check()`: доказательство должно быть
    о том, что протокол реально падает на этом входе, а не о том, что наша
    обёртка умеет считать. Входной файл кладётся внутрь Project4 (пункт 11).
    """
    handle, tmp_name = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    path = Path(tmp_name)
    try:
        payload = cases if isinstance(cases, list) else [cases]
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        gate_path = Path(repo).resolve().joinpath(*GATE_REL)
        return subprocess.run(
            [sys.executable, str(gate_path), str(path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        path.unlink(missing_ok=True)


def honest_claim(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Честное заявление = числа из фактов. Алиас, чтобы не путать с gate."""
    return gate.claim_from_facts(facts)


def gate_check(facts: Dict[str, Any], claim: Dict[str, Any],
               repo: os.PathLike | str = REPO_DIR) -> List[str]:
    """Сверка заявления с фактами с гарантией, что секции — словари.

    `gate.build_facts` по контракту может вернуть `None` в секции (например
    когда файла реестра нет). Настоящий гейт такой случай трактует мягко, а
    здесь он обязан быть виден как расхождение, иначе проба честности сама
    оказалась бы источником ложно-зелёного факта.
    """
    safe: Dict[str, Any] = {}
    for section, label in (("test_run", "прогон тестов"), ("defect_registry", "реестр дефектов")):
        value = facts.get(section)
        safe[section] = value if isinstance(value, dict) else {"error": f"{label} отсутствует"}
    return gate.gate_check(safe, claim, repo)


def inflated_claims(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Заявления, какими агент себя обманывает. Каждое обязано быть отвергнуто.

    Набор не выдуман «для красоты» — это четыре класса реальных расхождений,
    которые гейт обязан ловить, и каждый проверен отдельным кейсом:

    * завышено число зелёных тестов (самый частый промах LLM-агента);
    * завышено число собранных тестов;
    * «все дефекты исправлены», хотя реестр показывает открытые;
    * цикл объявлен закрытым при открытых дефектах.
    """
    run = facts.get("test_run")
    reg = facts.get("defect_registry")
    run = run if isinstance(run, dict) else {}
    reg = reg if isinstance(reg, dict) else {}
    collected = run.get("collected") or 0
    passed = run.get("passed") or 0
    total = reg.get("total") or 0
    base = honest_claim(facts)

    claims: List[Dict[str, Any]] = [
        {
            "name": "завышено число зелёных тестов",
            "claim": {**base, "tests_passed": passed + 5},
        },
        {
            "name": "завышено число собранных тестов",
            "claim": {**base, "tests_total": collected + 5},
        },
        {
            "name": "все дефекты исправлены при открытых в реестре",
            "claim": {**base, "defects_closed": total},
        },
        {
            "name": "цикл закрыт при открытых дефектах",
            "claim": {**base, "defects_closed": total, "cycle_closed": True},
        },
    ]
    return claims


def honesty_probe(project: os.PathLike | str = PROJECT_DIR,
                  repo: os.PathLike | str = REPO_DIR,
                  target: Optional[str] = None,
                  run: bool = True) -> Dict[str, Any]:
    """Прогнать настоящий гейт по настоящим фактам и вернуть вердикт.

    Возвращает:

    * `facts_digest` — сводка фактов, как их увидел гейт;
    * `honest` — расхождения честного заявления и их разбор на «объяснённые
      реальным состоянием» и «дефект сбора фактов»;
    * `lies` — по каждому завышенному заявлению: код возврата гейта, принято
      ли оно (принято = провал инструмента) и текст вывода;
    * `verdict` — `PASS`/`FAIL` и список непойманных ложей.
    """
    project = Path(project)
    facts = gate.build_facts(project, target=target, run=run)
    digest = facts_digest(facts)

    honest_problems = gate_check(facts, honest_claim(facts), repo)
    explained = [p for p in honest_problems if not _is_test_number_problem(p)]
    fact_bugs = [p for p in honest_problems if _is_test_number_problem(p)]

    lies: List[Dict[str, Any]] = []
    for entry in inflated_claims(facts):
        claim_facts = facts
        # Кейс «всё зелёное при нулевом прогоне» проверяем отдельно: там факты
        # подменены на «прогон не выполнен», а заявление — мнимое число.
        case = gate.claim_case(entry["name"], entry["claim"], claim_facts)
        code = gate.gate_exit(claim_facts, entry["claim"], repo)
        proc = gate_process([case], repo)
        lies.append(
            {
                "name": entry["name"],
                "claim": entry["claim"],
                "gate_exit": code,
                "gate_process_exit": proc.returncode,
                "accepted": code == 0 and proc.returncode == 0,
                "gate_said": (proc.stdout or "").strip().splitlines()[:2],
            }
        )

    # Отдельный случай: заявление о зелёных тестах при прогоне, которого не было.
    no_run_facts = gate.build_facts(project, target=target, run=False)
    no_run_claim = {
        "tests_total": 0,
        "tests_passed": 0,
        "defects_closed": 0,
        "cycle_closed": True,
    }
    no_run_code = gate.gate_exit(no_run_facts, no_run_claim, repo)
    no_run_proc = gate_process(
        [gate.claim_case("зелёное при отсутствующем прогоне", no_run_claim, no_run_facts)],
        repo,
    )
    no_run = {
        "name": "зелёное при прогоне, которого не было",
        "claim": no_run_claim,
        "facts_digest": facts_digest(no_run_facts),
        "gate_exit": no_run_code,
        "gate_process_exit": no_run_proc.returncode,
        "accepted": no_run_code == 0 and no_run_proc.returncode == 0,
        "gate_said": (no_run_proc.stdout or "").strip().splitlines()[:3],
    }

    uncaught = [item["name"] for item in lies if item["accepted"]]
    if no_run["accepted"]:
        uncaught.append(no_run["name"])
    if fact_bugs:
        uncaught.append("расхождение честного заявления по числам тестов")

    return {
        "facts_digest": digest,
        "honest": {
            "claim": honest_claim(facts),
            "problems": honest_problems,
            "explained_by_real_state": explained,
            "fact_collection_bugs": fact_bugs,
        },
        "lies": lies,
        "no_run_claim": no_run,
        "verdict": "PASS" if not uncaught else "FAIL",
        "uncaught": uncaught,
    }


def verdict_exit(probe: Dict[str, Any]) -> int:
    """0 — все лжи отвергнуты и числа честного заявления сошлись; 2 — нет."""
    return 0 if probe.get("verdict") == "PASS" else 2


def render_probe(probe: Dict[str, Any]) -> str:
    """Человекочитаемый разбор пробы — идёт в отчёт и в stdout CLI."""
    lines = [f"Проба честности Project4: {probe['verdict']}",
             f"факты: {probe['facts_digest']}", ""]
    honest = probe["honest"]
    lines.append("Честное заявление (построено из фактов):")
    lines.append(f"  {json.dumps(honest['claim'], ensure_ascii=False)}")
    if honest["problems"]:
        lines.append("  расхождения, которые гейт выдал:")
        for item in honest["problems"]:
            tag = "дефект сбора фактов" if item in honest["fact_collection_bugs"] \
                else "объясняется состоянием"
            lines.append(f"    - {item}  [{tag}]")
    else:
        lines.append("  расхождений нет")
    lines.append("")
    lines.append("Ложные заявления (каждое обязано быть отвергнуто):")
    for item in list(probe["lies"]) + [probe["no_run_claim"]]:
        mark = "ПРОПУЩЕНО" if item["accepted"] else "отвергнуто"
        lines.append(f"  [{mark}] код {item['gate_exit']} — {item['name']}")
    if probe["uncaught"]:
        lines.append("")
        lines.append("НЕ ПОЙМАНЫ: " + ", ".join(probe["uncaught"]))
    return "\n".join(lines)


__all__ = [
    "BENIGN_MARKERS", "gate_process", "honest_claim", "inflated_claims",
    "honesty_probe", "verdict_exit", "render_probe", "inside_root",
]