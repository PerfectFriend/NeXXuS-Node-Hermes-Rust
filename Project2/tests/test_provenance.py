"""Тесты диагностики происхождения и информативности полей (Фаза 2)."""

from p2_graph.provenance import (
    CONSTANT_SHARE,
    dedupe_by_freshness,
    field_profile,
    file_freshness,
    file_order_report,
    insight_freshness,
    origin_findings,
    parse_ts,
    relevance_informative,
)


def _ins(**kw):
    base = {"topic": "t", "source_url": "u", "timestamp": "2026-01-01T00:00:00+00:00"}
    base.update(kw)
    return base


# --- parse_ts / insight_freshness ---


def test_parse_ts_разбирает_iso():
    assert parse_ts("2026-01-02T03:04:05+00:00") is not None


def test_parse_ts_возвращает_none_на_мусоре():
    assert parse_ts("не дата") is None
    assert parse_ts(None) is None


def test_insight_freshness_читает_synced_at():
    # synced_at — свойство ФАЙЛА, а не записи: в самой записи он не читается.
    got = insight_freshness({"topic": "t", "source_url": "u",
                             "synced_at": "2026-02-02T00:00:00+00:00"})
    assert got is None
    # Свежесть содержащего файла приходит отдельным аргументом.
    assert insight_freshness({"topic": "t", "source_url": "u"},
                             fallback=parse_ts("2026-02-02T00:00:00+00:00")) == parse_ts(
        "2026-02-02T00:00:00+00:00")


def test_insight_freshness_учитывает_fallback():
    assert insight_freshness(_ins(timestamp=None), fallback=1000.0) == 1000.0


def test_insight_freshness_без_источников_даёт_none():
    assert insight_freshness(_ins(timestamp=None)) is None


def test_file_freshness_читает_synced_at():
    assert file_freshness({"synced_at": "2026-01-01T00:00:00+00:00"}) is not None


# --- dedupe_by_freshness ---


def test_свежая_копия_вытесняет_старую():
    items = [
        _ins(timestamp="2026-01-01T00:00:00+00:00", mark="старая"),
        _ins(timestamp="2026-03-01T00:00:00+00:00", mark="свежая"),
    ]
    kept, stats = dedupe_by_freshness(items)
    assert [k["mark"] for k in kept] == ["свежая"]
    assert stats["replaced"] == 1
    assert stats["kept"] == 1


def test_старая_копия_не_переигрывает():
    items = [
        _ins(timestamp="2026-03-01T00:00:00+00:00", mark="свежая"),
        _ins(timestamp="2026-01-01T00:00:00+00:00", mark="старая"),
    ]
    kept, stats = dedupe_by_freshness(items)
    assert [k["mark"] for k in kept] == ["свежая"]
    assert stats["replaced"] == 0


def test_разные_ключи_не_сливаются():
    kept, stats = dedupe_by_freshness(
        [_ins(topic="a"), _ins(topic="b", source_url="v")]
    )
    assert len(kept) == 2
    assert stats["replaced"] == 0


def test_без_даты_проигрывает_датированной():
    items = [_ins(timestamp=None), _ins(timestamp="2026-01-01T00:00:00+00:00")]
    kept, stats = dedupe_by_freshness(items)
    assert kept[0]["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert stats["unparsable"] == 1


def test_подставленная_свежесть_вытесняет_датированную_и_считается_stale():
    items = [
        _ins(timestamp="2026-01-01T00:00:00+00:00", mark="датированная"),
        _ins(timestamp=None, mark="из_файла"),
    ]
    kept, stats = dedupe_by_freshness(items, fallback=9e9)
    assert [k["mark"] for k in kept] == ["из_файла"]
    assert stats["stale_wins"] == 1
    assert stats["undated_wins"] == 1
    assert stats["replaced"] == 1


def test_подставленная_свежесть_против_бездаты_не_даёт_stale():
    items = [
        _ins(timestamp=None, mark="без_даты"),
        _ins(timestamp=None, mark="из_файла"),
    ]
    kept, stats = dedupe_by_freshness(items, fallback=9e9)
    assert [k["mark"] for k in kept] == ["из_файла"]
    assert stats["stale_wins"] == 0
    assert stats["undated_wins"] == 1


def test_мусор_в_потоке_пропускается():
    # Поток специально смешанного типа: мусор обязан отбрасываться, а не ронять сборку.
    kept, stats = dedupe_by_freshness([None, "строка", 42, _ins()])  # type: ignore[list-item]
    assert len(kept) == 1


def test_пустой_поток():
    kept, stats = dedupe_by_freshness([])
    assert kept == []
    assert stats["kept"] == 0


def test_порядок_первого_появления_сохраняется():
    items = [_ins(topic="поздний"), _ins(topic="ранний")]
    kept, _ = dedupe_by_freshness(items)
    assert [k["topic"] for k in kept] == ["поздний", "ранний"]


# --- file_order_report ---


def test_порядок_файлов_по_умолчанию_хронологический():
    rows = file_order_report([])
    assert rows == []


def test_порядок_файлов_ловит_инверсию():
    # Файлы приходят в порядке чтения; инверсия — файл читается РАНЬШЕ более свежего.
    rows = file_order_report(
        [
            {"_path": "старее.md", "_cycle": 2, "synced_at": "2026-01-01T00:00:00+00:00"},
            {"_path": "новее.md", "_cycle": 1, "synced_at": "2026-03-01T00:00:00+00:00"},
        ]
    )
    assert rows[0]["inverted"] is False
    assert rows[1]["inverted"] is True
    assert rows[1]["newer_before"] is not None


def test_порядок_файлов_без_synced_at_не_врёт():
    rows = file_order_report([{"_path": "a.md"}, {"_path": "b.md"}])
    assert all(row["inverted"] is False for row in rows)


def test_порядок_файлов_считает_номер_цикла():
    rows = file_order_report([{"_path": "cycle_012_insights.md", "synced_at": "2026-01-01T00:00:00+00:00"}])
    assert rows[0]["cycle"] == 12
    assert rows[0]["insights"] == 0


# --- field_profile ---


def test_профиль_поля_видит_постоянство():
    prof = field_profile([{"category": "a"}, {"category": "a"}, {"category": "a"}], ("category",))[0]
    assert prof["distinct"] == 1
    assert prof["constant"] is True


def test_профиль_поля_видит_разнообразие():
    prof = field_profile([{"category": "a"}, {"category": "b"}], ("category",))[0]
    assert prof["distinct"] == 2
    assert prof["constant"] is False


def test_профиль_пустого_поля_не_врёт():
    prof = field_profile([{}], ("category",))[0]
    assert prof["distinct"] == 1  # одно значение — отсутствие поля
    assert prof["constant"] is True


def test_профиль_на_пустом_потоке():
    prof = field_profile([], ("category",))[0]
    assert prof["distinct"] == 0
    assert prof["constant"] is False


def test_профиль_разбирает_списки():
    rows = field_profile([{"tags": ["a", "b"]}, {"tags": ["c"]}], ("tags",))
    assert rows[0]["distinct"] == 2


# --- relevance_informative ---


def test_одинаковые_relevance_неинформативны():
    ok, spread = relevance_informative([{"relevance_score": 0.9}, {"relevance_score": 0.9}])
    assert ok is False
    assert spread == 0.0
    assert CONSTANT_SHARE == 0.9


def test_разные_relevance_информативны():
    ok, spread = relevance_informative([{"relevance_score": 0.9}, {"relevance_score": 0.1}])
    assert ok is True
    assert spread == 0.8


def test_одна_запись_не_даёт_вывода():
    ok, spread = relevance_informative([{"relevance_score": 0.9}])
    assert ok is False
    assert spread == 0.0


def test_мусорный_relevance_пропускается():
    ok, _ = relevance_informative([{"relevance_score": "высокая"}, {"relevance_score": True}])
    assert ok is False


# --- origin_findings ---


def test_учебник_на_соцсети_помечен():
    found = origin_findings([{"source_type": "textbook", "source_url": "https://vk.com/x"}])
    assert found and "соцсет" in found[0]["reasons"][0]


def test_учебник_вне_vault_помечен():
    found = origin_findings([{"source_type": "textbook", "source_url": "https://example.com/a"}])
    assert found


def test_учебник_из_vault_чист():
    found = origin_findings([{"source_type": "textbook", "source_url": "notes/a.md"}])
    assert found == []


def test_тема_от_навигационного_сканера_помечена():
    found = origin_findings([{"topic": "X: 2087163793558126997", "source_url": "u", "source_type": "wiki"}])
    assert found and "навигация" in found[0]["reasons"][0]


def test_чистая_запись_без_замечаний():
    found = origin_findings(
        [{"source_type": "wiki", "source_url": "notes/a.md", "topic": "Обычная тема"}]
    )
    assert found == []


def test_мусор_в_потоке_origin_пропускается():
    assert origin_findings([None, "строка"]) == []  # type: ignore[list-item]