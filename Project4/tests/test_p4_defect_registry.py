"""Пункт 15 плана: реестр дефектов Project4 — проверка согласованности.

Счётчики defect_registry, которые уходят в `tools/cycle_claim_gate.py`, обязаны
сходиться с суммой статусов в файле. Иначе агент может заявить «дефектов
закрыто N» и обойти сверку.
"""
import json
from pathlib import Path

import pytest

from p4_provenance import gate

PROJECT = Path(__file__).resolve().parent.parent


def test_registry_sums_are_consistent():
    reg = gate.read_registry(PROJECT)
    assert reg and "error" not in reg, f"реестр не читается: {reg}"
    counts = gate.registry_by_status(PROJECT)
    assert counts.get("open", 0) == reg["open"], (counts, reg)
    assert counts.get("closed", 0) == reg["closed"], (counts, reg)
    assert reg["open"] + reg["closed"] == reg["total"], reg


def test_registry_has_unique_ids():
    data = json.loads((PROJECT / gate.REGISTRY_NAME).read_text(encoding="utf-8"))
    ids = [d["id"] for d in data["defects"]]
    assert len(ids) == len(set(ids)), f"дубликаты id в реестре: {ids}"


def test_registry_items_have_required_fields():
    data = json.loads((PROJECT / gate.REGISTRY_NAME).read_text(encoding="utf-8"))
    for item in data["defects"]:
        for field in ("id", "title", "status", "detail"):
            assert item.get(field), f"дефект без поля {field}: {item}"


def test_broken_registry_does_not_report_zeroes(tmp_path):
    """Битый JSON — это ошибка, а не «дефектов ноль»."""
    (tmp_path / gate.REGISTRY_NAME).write_text("{не json", encoding="utf-8")
    reg = gate.read_registry(tmp_path)
    assert reg and "error" in reg, reg


@pytest.mark.xfail(strict=True, reason="P4-D6: дефект без status не считается ошибкой")
def test_registry_counts_unknown_status_exposes_gap(tmp_path):
    """Дефект без `status` обязан ломать согласованность, а не молчать.

    Пока `read_registry` считает `total` по числу элементов, а `open`/`closed` —
    только по известным статусам, такой дефект даёт несходящиеся счётчики
    (total=1 при open=closed=0). Это заведено как P4-D6; тест падает намеренно
    и служит регрессией на тихую потерю дефекта.
    """
    (tmp_path / gate.REGISTRY_NAME).write_text(
        json.dumps({"defects": [{"id": "D1"}]}), encoding="utf-8")
    reg = gate.read_registry(tmp_path)
    assert reg and "error" in reg, (
        f"дефект без status прошёл как обычный: {reg} — счётчики разъедутся "
        f"с заявлением агента (P4-D6)")