"""Пункт 19 плана: `--fix` по свежести — разметка вместо удаления."""

import io
import json
from contextlib import redirect_stdout

from p2_graph.cli import EXIT_DATA, EXIT_OK, main
from p2_graph.loader import load
from p2_graph.provenance import (
    MARK_ORIGIN,
    MARK_SUPERSEDED,
    apply_freshness_fix,
    origin_findings,
    plan_freshness_fix,
    stale_duplicates,
)


def _ins(**kw):
    base = {"topic": "t", "source_url": "u", "timestamp": "2026-01-01T00:00:00+00:00"}
    base.update(kw)
    return base


def _память(tmp_path, имя, цикл, synced, записи):
    payload = {"cycle": цикл, "project": 2, "synced_at": synced,
               "total_insights": len(записи), "insights": записи}
    путь = tmp_path / имя
    путь.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return путь


def _инверсный_корпус(tmp_path):
    """Два файла: второй читается позже, но старее, и содержит дубль."""
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00", [_ins()])
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-15T08:10:33+00:00", [_ins()])


# --- План разметки --------------------------------------------------------


def test_stale_duplicates_видит_запись_из_более_свежего_файла(tmp_path):
    _инверсный_корпус(tmp_path)
    from p2_graph.loader import load_all

    шаги = stale_duplicates(load_all(str(tmp_path)))
    assert len(шаги) == 1
    assert шаги[0]["kind"] == "superseded"
    assert "cycle_001" in шаги[0]["superseded_by"]


def test_stale_duplicates_молчит_на_хронологичном_корпусе(tmp_path):
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00", [_ins()])
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-17T08:10:33+00:00", [_ins()])
    from p2_graph.loader import load_all

    assert stale_duplicates(load_all(str(tmp_path))) == []


def test_план_разметки_считает_и_дубли_и_происхождение(tmp_path):
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00", [_ins()])
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-15T08:10:33+00:00",
            [_ins(), {"topic": "X: 2087163793558126997",
                      "source_url": "https://x.com/i/status/1",
                      "source_type": "textbook",
                      "timestamp": "2026-08-15T08:10:33+00:00"}])
    from p2_graph.loader import load_all

    план = plan_freshness_fix(load_all(str(tmp_path)))
    виды = sorted(s["kind"] for s in план)
    assert виды == ["origin", "superseded"]


def test_план_происхождения_адресован_своему_файлу(tmp_path):
    """Индексы origin-находок сквозные; в плане они должны быть внутри файла.

    Регресс: пометка, ушедшая в соседний файл, пометила бы чужую тему.
    """
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00", [_ins()])
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-15T08:10:33+00:00",
            [{"topic": "X: 2087163793558126997",
              "source_url": "https://x.com/i/status/1",
              "source_type": "textbook",
              "timestamp": "2026-08-15T08:10:33+00:00"}])
    from p2_graph.loader import load_all

    план = plan_freshness_fix(load_all(str(tmp_path)))
    шаг = next(s for s in план if s["kind"] == "origin")
    assert шаг["file"].endswith("cycle_002.json")
    данные = load(tmp_path / "professor_insights_cycle_002.json")
    помеченная = данные["insights"][шаг["index"]]
    assert помеченная["topic"] == "X: 2087163793558126997"


def test_apply_размечает_и_не_удаляет(tmp_path):
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-15T08:10:33+00:00", [_ins(), _ins(topic="вторая")])
    данные = load(tmp_path / "professor_insights_cycle_002.json")
    план = [{"kind": "superseded", "index": 0, "superseded_by": "f1.json",
             "superseded_by_synced_at": "2026-08-16T08:10:33+00:00"}]
    новые, сколько = apply_freshness_fix(данные, план)
    assert сколько == 1
    assert len(новые["insights"]) == 2
    assert MARK_SUPERSEDED in новые["insights"][0]
    assert MARK_SUPERSEDED not in новые["insights"][1]
    assert новые["total_insights"] == 2


def test_apply_не_мутирует_загруженный_объект(tmp_path):
    """Иначе dry-run, напечатанный до --fix, врал бы о состоянии файла."""
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-15T08:10:33+00:00", [_ins()])
    данные = load(tmp_path / "professor_insights_cycle_002.json")
    apply_freshness_fix(данные, [{"kind": "superseded", "index": 0,
                                 "superseded_by": "f1.json",
                                 "superseded_by_synced_at": "2026-08-16T08:10:33+00:00"}])
    assert MARK_SUPERSEDED not in данные["insights"][0]


def test_apply_игнорирует_выход_индекса_за_границы(tmp_path):
    _память(tmp_path, "professor_insights_cycle_002.json", 2,
            "2026-08-15T08:10:33+00:00", [_ins()])
    данные = load(tmp_path / "professor_insights_cycle_002.json")
    новые, сколько = apply_freshness_fix(данные, [{"kind": "superseded", "index": 99,
                                                   "superseded_by": "f1.json"}])
    assert сколько == 0
    assert MARK_SUPERSEDED not in новые["insights"][0]


def test_origin_находка_пропадает_после_подтверждения():
    запись = _ins(topic="X: 2087163793558126997",
                  source_url="https://x.com/i/status/1", source_type="textbook")
    assert len(origin_findings([запись])) == 1
    подтверждена = dict(запись)
    подтверждена[MARK_ORIGIN] = origin_findings([запись])[0]["reasons"]
    assert origin_findings([подтверждена]) == []


def test_origin_новая_причина_не_списывается_старой_пометкой():
    """Старая пометка не должна закрывать новую подмену в той же записи."""
    запись = _ins(topic="X: 2087163793558126997",
                  source_url="https://x.com/i/status/1", source_type="textbook")
    запись[MARK_ORIGIN] = ["что-то другое совсем"]
    assert len(origin_findings([запись])) == 1


# --- CLI -----------------------------------------------------------------


def test_cli_fix_перезаписывает_атомарно_и_даёт_бэкап(tmp_path):
    _инверсный_корпус(tmp_path)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness", "--fix", "--json"])
    данные = json.loads(буфер.getvalue())
    assert данные["fixed_files"], "ничего не записано"
    цель = tmp_path / "professor_insights_cycle_002.json"
    assert (tmp_path / "professor_insights_cycle_002.json.bak").exists()
    assert not list(tmp_path.glob("*.tmp")), "остался временный файл"
    помеченная = load(цель)["insights"][0]
    assert MARK_SUPERSEDED in помеченная
    assert код == EXIT_OK, "после fix потерь быть не должно"


def test_cli_fix_повторный_прогон_даёт_ноль(tmp_path):
    _инверсный_корпус(tmp_path)
    with redirect_stdout(io.StringIO()):
        main(["--memory-dir", str(tmp_path), "freshness", "--fix", "--json"])
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness", "--json"])
    данные = json.loads(буфер.getvalue())
    assert данные["lost"] == 0
    assert данные["fix_plan"] == 0, "повторная разметка должна быть пустой"
    assert код == EXIT_OK


def test_cli_fix_закрывает_подмену_происхождения(tmp_path):
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00",
            [{"topic": "X: 2087163793558126997",
              "source_url": "https://x.com/i/status/1",
              "source_type": "textbook",
              "timestamp": "2026-08-16T08:10:33+00:00"}])
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        main(["--memory-dir", str(tmp_path), "freshness", "--fix", "--json"])
    буфер2 = io.StringIO()
    with redirect_stdout(буфер2):
        код = main(["--memory-dir", str(tmp_path), "freshness", "--json"])
    данные = json.loads(буфер2.getvalue())
    assert данные["origin_count"] == 0
    assert код == EXIT_OK
    assert MARK_ORIGIN in load(tmp_path / "professor_insights_cycle_001.json")["insights"][0]


def test_cli_dry_run_ничего_не_пишет(tmp_path):
    _инверсный_корпус(tmp_path)
    до = (tmp_path / "professor_insights_cycle_002.json").read_text(encoding="utf-8")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness", "--json"])
    данные = json.loads(буфер.getvalue())
    assert данные["fix_superseded"] == 1
    assert данные["fixed_files"] == []
    assert (tmp_path / "professor_insights_cycle_002.json").read_text(encoding="utf-8") == до
    assert код == EXIT_DATA, "без fix потери ещё на месте"


def test_cli_fix_текст_печатает_режим(tmp_path):
    _инверсный_корпус(tmp_path)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        main(["--memory-dir", str(tmp_path), "freshness", "--fix"])
    assert "Разметка" in буфер.getvalue()
    assert "записан" in буфер.getvalue()


def test_cli_fix_на_пустой_папке_не_ломается(tmp_path):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness", "--fix"])
    assert код == EXIT_DATA