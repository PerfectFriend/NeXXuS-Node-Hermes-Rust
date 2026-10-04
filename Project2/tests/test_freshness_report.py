"""Пункт 20 плана: FRESHNESS_REPORT.md — числа те же, что у кода."""

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

from p2_graph.cli import EXIT_DATA, EXIT_OK, main, render_freshness_report
from p2_graph.loader import load_all

from test_fix import _инверсный_корпус, _память


def _число(текст, метка):
    """Достать N из строки «- метка: N» отчёта."""
    m = re.search(rf"^- {re.escape(метка)}: (\d+)$", текст, re.M)
    assert m, f"в отчёте нет строки «- {метка}: N»"
    return int(m.group(1))


def _cli_json(tmp_path, *флаги):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness", "--json", *флаги])
    return json.loads(буфер.getvalue()), код


# --- Сверка чисел с прогоном freshness --json -----------------------------


def test_числа_отчёта_совпадают_с_json_на_свежем_корпусе(tmp_path):
    _инверсный_корпус(tmp_path)
    текст = render_freshness_report(load_all(str(tmp_path)))
    данные, _ = _cli_json(tmp_path)
    assert _число(текст, "файлов памяти") == len(load_all(str(tmp_path)))
    assert _число(текст, "инверсий") == данные["inverted_count"]
    assert _число(текст, "всего неразмеченных потерь") == данные["lost"]
    assert _число(текст, "находок") == данные["origin_count"]


def test_числа_отчёта_совпадают_с_json_после_fix(tmp_path):
    """Главная проверка пункта: файл не может разойтись с кодом."""
    _инверсный_корпус(tmp_path)
    with redirect_stdout(io.StringIO()):
        main(["--memory-dir", str(tmp_path), "freshness", "--fix", "--json"])
    текст = render_freshness_report(load_all(str(tmp_path)))
    данные, код = _cli_json(tmp_path)
    assert данные["lost"] == 0
    assert _число(текст, "всего неразмеченных потерь") == 0
    assert _число(текст, "находок") == данные["origin_count"]
    assert код == EXIT_OK


def test_отчёт_показывает_и_помеченное_и_непомеченное(tmp_path):
    _инверсный_корпус(tmp_path)
    до = render_freshness_report(load_all(str(tmp_path)))
    assert _число(до, "всего неразмеченных потерь") == 1
    assert _число(до, "помечено как устаревшие дубли, всего по корпусу") == 0
    with redirect_stdout(io.StringIO()):
        main(["--memory-dir", str(tmp_path), "freshness", "--fix", "--json"])
    после = render_freshness_report(load_all(str(tmp_path)))
    assert _число(после, "всего неразмеченных потерь") == 0
    assert _число(после, "помечено как устаревшие дубли, всего по корпусу") == 1


def test_отчёт_перечисляет_находки_происхождения(tmp_path):
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00",
            [{"topic": "X: 2087163793558126997",
              "source_url": "https://x.com/i/status/1",
              "source_type": "textbook",
              "timestamp": "2026-08-16T08:10:33+00:00"}])
    текст = render_freshness_report(load_all(str(tmp_path)))
    assert _число(текст, "находок") == 1
    assert "X: 2087163793558126997" in текст
    assert "навигация сканера" in текст


def test_отчёт_имеет_шапку_и_предупреждение(tmp_path):
    _инверсный_корпус(tmp_path)
    текст = render_freshness_report(load_all(str(tmp_path)))
    assert текст.startswith("# Свежесть корпуса Project2")
    assert "Не редактировать руками" in текст
    assert "## Что из этого следует" in текст


def test_отчёт_на_хронологичном_корпусе_говорит_что_инверсий_нет(tmp_path):
    _память(tmp_path, "professor_insights_cycle_001.json", 1,
            "2026-08-16T08:10:33+00:00", [{"topic": "t", "source_url": "u",
                                          "timestamp": "2026-08-16T08:10:33+00:00"}])
    текст = render_freshness_report(load_all(str(tmp_path)))
    assert _число(текст, "инверсий") == 0
    assert "порядок чтения совпадает с хронологией: True" in текст


# --- Команда ---------------------------------------------------------------


def test_команда_пишет_файл_и_печатает_путь(tmp_path):
    _инверсный_корпус(tmp_path)
    цель = tmp_path / "FRESHNESS_REPORT.md"
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness-report", "--out", str(цель)])
    assert код == EXIT_OK
    assert цель.exists()
    assert str(цель) in буфер.getvalue()
    assert цель.read_text(encoding="utf-8") == render_freshness_report(
        load_all(str(tmp_path))
    )


def test_команда_перезаписывает_файл_целиком(tmp_path):
    """Правки руками не должны выживать между прогонами."""
    _инверсный_корпус(tmp_path)
    цель = tmp_path / "FRESHNESS_REPORT.md"
    цель.write_text("вредная правка", encoding="utf-8")
    with redirect_stdout(io.StringIO()):
        main(["--memory-dir", str(tmp_path), "freshness-report", "--out", str(цель)])
    assert "вредная правка" not in цель.read_text(encoding="utf-8")


def test_команда_на_пустой_папке(tmp_path):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = main(["--memory-dir", str(tmp_path), "freshness-report",
                    "--out", str(tmp_path / "X.md")])
    assert код == EXIT_DATA
    assert not (tmp_path / "X.md").exists()


def test_команда_кладёт_файл_рядом_с_пакетом_по_умолчанию(tmp_path):
    """Путь по умолчанию — как у GRAPH_REPORT.md, чтобы искать было привычно."""
    _инверсный_корпус(tmp_path)
    цель = Path("/home/thomas/LivingCode/Project2/FRESHNESS_REPORT.md")
    было = цель.read_text(encoding="utf-8") if цель.exists() else None
    try:
        with redirect_stdout(io.StringIO()):
            main(["--memory-dir", str(tmp_path), "freshness-report"])
        assert цель.exists()
    finally:
        if было is None:
            цель.unlink(missing_ok=True)
        else:
            цель.write_text(было, encoding="utf-8")