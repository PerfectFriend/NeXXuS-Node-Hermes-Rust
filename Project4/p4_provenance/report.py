"""Генерация PROVENANCE_REPORT.md из посчитанных данных (пункт 9 плана).

Правило жёсткое: в отчёте нет ни одной константы, написанной руками. Каждое
число приходит из модулей пакета, поэтому отчёт расходится с кодом только если
разошлись сами данные — и тогда это видно, а не спрятано.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from . import SIBLING_PROJECTS
from .attribution import attribute_corpus, default_addressing_audit, repetition_report
from .canary import canary
from .canary import line as canary_line
from .fingerprint import corpus_fingerprints, identity_report
from .loader import iter_records, validate_corpus
from .metrics import metrics, unique_filter_values
from .repro import repro_report

TITLE = "PROVENANCE_REPORT.md — форензика памяти Project4"


def _table(headers: List[str], rows: Iterable[List[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def render_report(
    directory: os.PathLike | str,
    repo: os.PathLike | str,
    names: Iterable[str] = SIBLING_PROJECTS,
    repro_enabled: bool = True,
) -> str:
    """Собрать полный отчёт. Каждое число — результат вызова, не литерал."""
    records = iter_records(directory)
    validation = validate_corpus(directory)
    fingerprints = corpus_fingerprints(directory)
    identity = identity_report(directory, repo, names=names)
    addressing = default_addressing_audit(records)
    ownership = attribute_corpus(records)
    repeats = repetition_report(records)
    stats = metrics(records)
    values = unique_filter_values(records)
    canary_report = canary(directory, repo, names=names)
    repro = repro_report(repo) if repro_enabled else None

    out: List[str] = [f"# {TITLE}", ""]

    out += [
        "## 1. Состояние корпуса",
        "",
        _table(
            ["Показатель", "Значение"],
            [
                ["Файлов памяти", validation["files"]],
                ["Записей всего", validation["records"]],
                ["Циклов", len(fingerprints)],
                ["Претензий валидации", validation["problem_count"]],
                ["Уникальных тем", repeats["unique_topics"]],
                ["Записей-повторов", repeats["duplicate_records"]],
                ["Пустых тем", stats["empty_topics"]],
                ["Корпус валиден", "да" if validation["valid"] else "нет"],
            ],
        ),
        "",
    ]

    out += ["### Отпечатки циклов", ""]
    out += [
        _table(
            ["Цикл", "Записей", "SHA-256 тела (первые 16)", "Проект в файле"],
            [
                [info["cycle"], info["records"], info["digest"][:16], info["project"]]
                for _, info in sorted(fingerprints.items(), key=lambda kv: str(kv[0]))
            ],
        ),
        "",
        "Отпечаток считается по каноническому телу инсайтов без полей "
        "`project` и `synced_at`: одинаковое содержание даёт одинаковый хэш "
        "независимо от приписей о доставке.",
        "",
    ]

    out += [
        "## 2. Кросс-проектная идентичность",
        "",
        f"Project4 идентичен: {', '.join(identity['identical_to']) or 'никому'}.",
        "",
        _table(
            ["Сосед", "Общих циклов", "Совпало отпечатков", "Расхождений", "Только у соседа", "Жаккар ключей"],
            [
                [
                    name,
                    len(info["body"]["shared_cycles"]),
                    len(info["body"]["identical_cycles"]),
                    len(info["body"]["divergent_cycles"]),
                    len(info["body"]["only_other"]),
                    info["keys"]["jaccard"],
                ]
                for name, info in identity["neighbours"].items()
                if info.get("present")
            ],
        ),
        "",
    ]

    out += [
        "## 3. Адресация записей",
        "",
        _table(
            ["Показатель", "Значение"],
            [
                ["Записей", addressing["records"]],
                ["С дефолтной адресацией", addressing["default_addressed"]],
                ["Доля дефолта", addressing["default_share"]],
                ["Ожидаемый дефолт синхронизатора", addressing["expected_default"]],
                ["Может ли фильтр различать проекты", "да" if addressing["filter_can_discriminate"] else "нет"],
            ],
        ),
        "",
        "Фильтр может различать проекты: "
        + ("нет" if not addressing["filter_can_discriminate"] else "да")
        + ".",
        "",
    ]

    if repro is not None:
        broken = repro["default_addressing_case"]
        control = repro["real_addressing_control"]
        out += [
            "## 4. Живое воспроизведение дефекта адресации",
            "",
            f"Горячий код импортирован без правок: `{broken['hot_source_line']}`.",
            "",
            "Прогон на синтетическом наборе без поля `applicable_projects`:",
            "",
            _table(
                ["Проект", "Записей синхронизировано"],
                [[name, count] for name, count in broken["synced_per_project"].items()],
            ),
            "",
            f"Запись без адресации ушла во все проекты: "
            f"{'да' if broken['leaked_everywhere'] else 'нет'}. "
            f"Присвоенная адресация `{broken['default_addressing']}`.",
            "",
            "Контрольный прогон с реально различающейся адресацией:",
            "",
            _table(
                ["Показатель", "Значение"],
                [
                    ["Синхронизировано в Project4", control["project4_synced"]],
                    ["Синхронизировано в Project2", control["project2_synced"]],
                    ["Фильтр отбирает верно", "да" if control["filter_works"] else "нет"],
                ],
            ),
            "",
            f"**Вывод:** {repro['diagnosis']}. Дефект подтверждён: "
            f"{'да' if repro['defect_confirmed'] else 'нет'}.",
            "",
            "Правка горячего файла — не скоум Project4.",
            "",
        ]

    out += ["## 5. Происхождение записей", ""]
    out += [
        _table(
            ["Группа", "Записей", "Доля", "Циклы"],
            [
                [name, group["count"], group["share"], ", ".join(map(str, group["cycles"]))]
                for name, group in ownership["groups"].items()
            ],
        ),
        "",
        _table(
            ["Показатель", "Значение"],
            [
                ["Учебно-дайджестовое ядро", ownership["core_total"]],
                ["Доля ядра", ownership["core_share"]],
                ["Проектные записи", ownership["own_total"]],
                ["Явно адресованные", ownership["explicitly_addressed"]],
            ],
        ),
        "",
        f"**Вывод:** {ownership['verdict']}.",
        "",
        "Принадлежность выводится из служебных меток (`source_type`, теги, "
        "категория), а не из темы и не из `applicable_projects`: тема «Graph "
        "Engineering Fundamentals» — это учебник, а не достояние Project2, а "
        "поле адресации у всех записей равно дефолту.",
        "",
    ]

    out += [
        "## 6. Метрики корпуса",
        "",
        _table(
            ["Показатель", "Значение"],
            [
                ["Записей", stats["records"]],
                ["Циклов", stats["cycle_count"]],
                ["Записей по циклам", stats["per_cycle"]],
                ["Категории", stats["categories"]],
                ["Типы источников", stats["source_types"]],
                ["Уникальных тем", stats["unique_topics"]],
                ["Доля повторов", stats["duplicate_share"]],
                ["Пустых тем", stats["empty_topics"]],
                ["Распределение релевантности", stats["relevance"]],
                ["Пропуски полей", stats["missing_fields"]],
            ],
        ),
        "",
    ]

    out += [
        "## 7. Канарейка",
        "",
        _table(["Проверка", "Результат"], [[name, "OK" if ok else "НЕ ОК"] for name, ok in canary_report["checks"].items()]),
        "",
        f"Вердикт: **{canary_report['status']}** — {canary_line(canary_report)}",
        "",
    ]

    out += [
        "## 8. Значения фильтров",
        "",
        f"- Категории: {', '.join(values['categories'])}",
        f"- Типы источников: {', '.join(values['source_types'])}",
        f"- Теги: {', '.join(values['tags'])}",
        "",
    ]

    if validation["problems"]:
        out += ["## Приложение. Претензии валидации", ""]
        out += [f"- {problem}" for problem in validation["problems"][:50]]
        out += [""]

    return "\n".join(out) + "\n"


def report_facts(directory: os.PathLike | str, repo: os.PathLike | str) -> Dict[str, Any]:
    """Числа отчёта как словарь — для регрессионного теста и для canary."""
    records = iter_records(directory)
    return {
        "records": len(records),
        "cycles": len(corpus_fingerprints(directory)),
        "valid": validate_corpus(directory)["valid"],
        "identity": identity_report(directory, repo)["identical_to"],
        "addressing": default_addressing_audit(records)["default_share"],
        "core_share": attribute_corpus(records)["core_share"],
        "unique_topics": repetition_report(records)["unique_topics"],
    }