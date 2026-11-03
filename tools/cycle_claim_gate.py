#!/usr/bin/env python3
"""Сверяющий гейт «цикл закрыт» — детерминированная замена LLM-заявлениям агента.

Проблема, которую он закрывает: tracelint (8 правил, judge-free) проверен живьём и
НЕ ловит ложное утверждение агента вида «101/101 тестов зелёные, все 10 дефектов
исправлены». Все правила tracelint проверяют форму вызова, а не смысл утверждения.

Этот гейт работает наоборот: он не ищет промахи в структуре, а сверяет ЗАЯВЛЕНИЕ агента
с ФАКТИЧЕСКИМ состоянием из машинных источников и падает, если расхождение.

Вход (JSON):
  {
    "claim": {"tests_total": 101, "tests_passed": 101, "defects_closed": 10,
              "cycle_closed": true},
    "facts":  {"test_run": {"passed": 100, "failed": 1, "collected": 101},
               "defect_registry": {"open": 2, "closed": 8, "total": 10}}
  }

Код возврата: 0 — заявление подтверждено фактами, 2 — расхождение (гейт роняет сборку).
Ни одного вызова LLM: только арифметика по числам, которые и так есть в системе.
"""
from __future__ import annotations

import json
import sys

TOLERANCE = 0  # ни одно расхождение в числах не прощается


def check(claim: dict, facts: dict) -> list[str]:
    """Возвращает список расхождений; пустой список — заявление подтверждено."""
    problems: list[str] = []

    run = facts.get("test_run")
    if run is None:
        problems.append("нет фактического прогона тестов — заявление о зелёных тестах "
                        "нечем подтвердить")
    else:
        passed, failed = run.get("passed"), run.get("failed")
        if passed != claim.get("tests_passed"):
            problems.append(f"заявлено тестов зелёных: {claim.get('tests_passed')}, "
                            f"фактически passed: {passed}")
        if failed:
            problems.append(f"фактический прогон содержит падений: {failed}")
        if run.get("collected") is not None and claim.get("tests_total") is not None:
            if run["collected"] != claim["tests_total"]:
                problems.append(f"заявлено всего тестов: {claim['tests_total']}, "
                                f"собрано прогоном: {run['collected']}")

    registry = facts.get("defect_registry")
    if registry is None:
        problems.append("нет реестра дефектов — заявление об исправлении всех дефектов "
                        "нечем подтвердить")
    else:
        if registry.get("open"):
            problems.append(f"в реестре осталось открытых дефектов: {registry['open']}")
        if claim.get("defects_closed") is not None:
            if registry.get("closed") != claim["defects_closed"]:
                problems.append(f"заявлено закрытых дефектов: {claim['defects_closed']}, "
                                f"по реестру: {registry.get('closed')}")

    perf = facts.get("performance")
    if perf is not None and isinstance(perf, dict) and not perf.get("error"):
        regression_count = perf.get("regression_count", 0)
        claimed = claim.get("perf_regressions")
        if claimed is not None and claimed != regression_count:
            problems.append(f"заявлено регрессий производительности: {claimed}, "
                            f"по сравнению с baseline: {regression_count}")
        elif claimed is None and regression_count:
            problems.append(f"секция performance показывает {regression_count} "
                            f"регрессий производительности, но perf_regressions не заявлен")
    elif perf is not None and isinstance(perf, dict) and perf.get("error"):
        if "perf_regressions" in claim:
            problems.append(f"заявление о производительности нечем подтвердить: {perf.get('error')}")
    elif "perf_regressions" in claim:
        problems.append("заявление о производительности нечем подтвердить: "
                        "секция производительности отсутствует")

    if claim.get("cycle_closed") and problems:
        problems.append("агент объявил закрытие цикла, хотя факты не подтверждают")

    return problems


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: cycle_claim_gate.py <claims.json>")
        return 0 if args else 64
    with open(args[0], encoding="utf-8") as f:
        payload = json.load(f)

    cases = payload if isinstance(payload, list) else [payload]
    all_problems: list[str] = []
    for case in cases:
        name = case.get("name", "без имени")
        problems = check(case.get("claim", {}), case.get("facts", {}))
        if problems:
            all_problems.extend(f"[{name}] {p}" for p in problems)
            print(f"ПРОВАЛ {name}:")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"ПОДТВЕРЖДЕНО {name}")

    if all_problems:
        print(f"\nИТОГ: {len(all_problems)} расхождение(й) — цикл закрывать нельзя.")
        return 2
    print("\nИТОГ: все заявления подтверждены фактами.")
    return 0


if __name__ == "__main__":
    sys.exit(main())