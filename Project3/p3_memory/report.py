"""Отчёт DUPLICITY_REPORT.md, порождённый кодом (пункт 9 плана).

Каждое число в отчёте — из посчитанного. Ручных констант нет: если корпус
поменяется, отчёт обязан поехать вместе с ним. Регрессионный тест сверяет
числа отчёта с независимым пересчётом.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .attribution import addressing_from_disk
from .canon import corpus
from .identity import identity_report
from .loader import DEFAULT_DIR, validate_corpus
from .metrics import metrics, report_path
from .paths import atomic_write

SYNC_DEFECT_LOC = "scripts/professor_sync.py:113, фильтр на строке 125"


def _table(rows: List[List[Any]], header: List[str]) -> List[str]:
    lines = ["| " + " | ".join(str(h) for h in header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


def build_report(memory_dir: Path = DEFAULT_DIR) -> str:
    """Собрать текст отчёта из данных."""
    m = metrics(memory_dir)
    ident = identity_report(memory_dir)
    addr = addressing_from_disk(memory_dir)
    val = validate_corpus(memory_dir)
    canon_result = corpus(memory_dir)

    lines: List[str] = []
    lines.append("# DUPLICITY_REPORT — Project3")
    lines.append("")
    lines.append("Отчёт порождён кодом (`p3_memory report`). Все числа посчитаны")
    lines.append("по корпусу `Project3/memory/`; ручных констант в тексте нет.")
    lines.append("")

    lines.append("## 1. Состояние корпуса")
    lines.append("")
    lines.extend(_table([
        ["файлов памяти", m["files"]],
        ["записей на входе", m["records_input"]],
        ["уникальных записей", m["records_total"]],
        ["снято повторов", m["duplicates_removed"]],
        ["тем-заглушек", f'{m["junk_topics"]} (доля {m["junk_ratio"]:.4f})'],
        ["валидация схемы", "чисто" if val["valid"] else f'{val["problem_count"]} претензий'],
    ], ["величина", "значение"]))
    lines.append("")

    lines.append("## 2. Релевантность")
    lines.append("")
    lines.extend(_table([
        ["минимум", m["score_min"]],
        ["среднее", m["score_mean"]],
        ["максимум", m["score_max"]],
        *[[name, count] for name, count in m["score_buckets"].items()],
    ], ["величина", "значение"]))
    lines.append("")

    lines.append("## 3. Кросс-проектная идентичность")
    lines.append("")
    lines.append("Два уровня ответа: **содержание** (совпадают ли сами записи) и")
    lines.append("**байты** (совпадают ли файлы). Расхождение байтов при совпадении")
    lines.append("содержания — это служебная надстройка соседа, а не другие данные.")
    lines.append("")
    ident_rows = []
    for name, res in ident["per_sibling"].items():
        if "error" in res:
            ident_rows.append([name, "ошибка", res["error"][:60], "—", "—"])
            continue
        if res["identical"]:
            verdict = "идентичен по содержанию"
        else:
            verdict = "отличается"
        if not res["byte_identical"]:
            overlay = res.get("service_overlay") or {}
            fields = ", ".join(f'{k}×{v}' for k, v in (overlay.get("fields") or {}).items())
            byte_part = f'нет ({fields})' if fields else "нет"
        else:
            byte_part = "да"
        ident_rows.append([
            name,
            verdict,
            f'{res["shared_keys"]}/{res["own_keys"]}',
            f'{res["jaccard"]:.4f}',
            byte_part,
        ])
    lines.extend(_table(ident_rows, ["сосед", "содержание", "общих ключей",
                                     "Жаккар", "байты равны"]))
    lines.append("")
    if ident["all_identical"]:
        lines.append(f'**Тело Project3 ({ident["own_records"]} записей) — идентично по '
                     f'содержанию ВСЕМ соседям без единого различия.** Собственных '
                     f'ключей, не встречающихся ни у соседа: {ident["distinct_keys"]}.')
        if ident["service_only_siblings"]:
            fields = ", ".join(f'`{k}`' for k in ident["service_overlay_fields"])
            lines.append("")
            lines.append(f'Оговорка: файлы совпадают байт в байт не со всеми — '
                         f'у {", ".join(ident["service_only_siblings"])} в записи '
                         f'есть служебная надстройка ({fields}), которой нет в '
                         f'Project3. Это пометка о происхождении записи, а не '
                         f'её содержимое: множества ключей совпадают полностью.')
    else:
        lines.append(f'Тело Project3 совпало с соседями: '
                     f'{", ".join(ident["identical_siblings"]) or "ни с одним"}. '
                     f'Собственных ключей: {ident["distinct_keys"]}.')
    lines.append("")
    lines.append("### 3.1. Чем именно разошлись тела")
    lines.append("")
    diverged = {
        name: res["divergence"] for name, res in ident["per_sibling"].items()
        if res.get("divergence")
    }
    if not diverged:
        lines.append("Содержательных расхождений не найдено ни с одним соседом —")
        lines.append("совпадает всё, кроме, возможно, служебной надстройки.")
    else:
        lines.append("Вердикт «отличается» без причины бесполезен, поэтому расхождения")
        lines.append("посчитаны по полям. Сопоставление — по каноническому ключу записи,")
        lines.append("служебная надстройка снята.")
        lines.append("")
        for name, div in sorted(diverged.items()):
            lines.append(f'**{name}** — сопоставлено записей: {div["records_compared"]}, '
                         f'расходящихся полей: {div["field_count"]}.')
            lines.append("")
            lines.extend(_table(
                [[field, count] for field, count in div["fields"].items()],
                ["поле", "записей с различием"],
            ))
            if div["only_own"] or div["only_other"]:
                lines.append("")
                lines.append(f'Ключей только у Project3: {len(div["only_own"])}; '
                             f'только у соседа: {len(div["only_other"])}.')
            for field, examples in div["samples"].items():
                lines.append("")
                lines.append(f'Пример по полю `{field}`:')
                for example in examples:
                    lines.append(f'  - {example}')
    lines.append("")

    lines.append("## 4. Аудит адресации")
    lines.append("")
    lines.extend(_table([
        ["записей всего", addr["total"]],
        ["с дефолтом «все проекты»", addr["default_addressed"]],
        ["доля дефолтных", f'{addr["default_ratio"]:.4f}'],
        ["различных адресаций, кроме дефолта",
         addr["distinct_non_default_addressing"]],
        ["фильтр проекта 3 способен что-то отсечь",
         "да" if addr["filter_works"] else "нет"],
        ["отсеял бы фильтр", addr["excluded_count"]],
    ], ["величина", "значение"]))
    lines.append("")
    lines.append(addr["verdict"] + ".")
    lines.append("")
    lines.append(f"Механика дефекта: `{SYNC_DEFECT_LOC}` — поле `applicable_projects`")
    lines.append("подставляется дефолтом `[1, 2, 3, 4]`, и условие фильтра становится")
    lines.append("тождественно истинным. Правка этого файла — не скоум `p3_memory`:")
    lines.append("это hot-код синхронизатора, решение за его владельцем.")
    lines.append("")

    lines.append("## 5. Атрибуция по содержанию")
    lines.append("")
    lines.append("`applicable_projects` для этой оценки непригоден (поле одинаково у всех),")
    lines.append("поэтому принадлежность определяется типу источника и тегам.")
    lines.append("")
    lines.extend(_table([
        ["own (признаки Project3 есть)", m["attribution_own"]],
        ["shared (только общие метки)", m["attribution_shared"]],
        ["без признаков", m["attribution_unattributed"]],
    ], ["класс", "записей"]))
    lines.append("")

    lines.append("## 6. Типы источников")
    lines.append("")
    lines.extend(_table(
        [[name, count] for name, count in m["by_source_type"].items()],
        ["source_type", "записей"],
    ))
    lines.append("")

    lines.append("## 7. Повторы по файлам")
    lines.append("")
    lines.extend(_table(
        [[name, count] for name, count in m["duplicates_by_file"].items()],
        ["файл", "повторов"],
    ))
    lines.append("")
    lines.append(f'Всего снято при канонизации: {m["duplicates_removed"]}; '
                 f'уникальных записей в корпусе: {m["records_total"]} '
                 f'(вход {m["records_input"]}).')
    lines.append("")
    return "\n".join(lines) + "\n"


def write_report(path: Path | None = None, memory_dir: Path = DEFAULT_DIR,
                  fix: bool = False):
    """Записать отчёт. Без `fix=True` только возвращает текст.

    При `fix=True` возвращает путь к бэкапу ПРЕДЫДУЩЕЙ версии или None,
    если файла раньше не было (нечего было отдавать под бэкап).
    """
    text = build_report(memory_dir)
    if not fix:
        return text
    target = path or report_path()
    return atomic_write(Path(target), text)