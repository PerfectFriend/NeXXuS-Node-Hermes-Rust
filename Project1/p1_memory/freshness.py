"""Сверка MEMORY_REPORT.md с живым прогоном.

Дефект, который закрывает модуль: отчёт качества памяти писался вручную в
слоте 2026-10-03 и к моменту следующего слота разошёлся с фактом — заявлял
49 тестов при 104 реальных и молчал про измеренные харнессом 1835 инсайтов
и 42 дубля. Ничто этого не ловило: `report` печатал числа, а отчёт лежал
рядом и не сверялся ни с чем.

Здесь сверка машинная: числа извлекаются из markdown-таблицы отчёта и
сравниваются с тем, что даёт `p1_memory.validate.summarize` по живым данным.
Расхождение — не «сломано», а повод переписать отчёт, поэтому модуль ничего
не пишет, только перечисляет.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .loader import iter_memory_files, load
from .validate import summarize

DEFAULT_REPORT = "MEMORY_REPORT.md"

# Числа отчёта: после имени файла идут всего/мусор/дубли/чистых.
_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TOTAL_RE = re.compile(r"ИТОГО", re.IGNORECASE)
# «49 зелёных», «104 теста» и т.п.
_TESTS_RE = re.compile(r"(\d+)\s+(?:зелёных\s+)?(?:тест|теста|тестов)\b")
# Вторая форма: «тесты `tests/test_p1_memory.py` — 49 зелёных», где число
# стоит ПОСЛЕ слова «тесты». Найдена пробой tests/probe_false_ok.py на живом
# MEMORY_REPORT.md: первая регулярка её не покрывала, поэтому сверка отдавала
# exit 0 при заведомо устаревшем числе тестов.
_COUNTED_RE = re.compile(
    r"(\d+)\s+(?:зелёных|зеленых|успешных|работающих|проверок|штук)\b",
    re.IGNORECASE,
)
_TEST_WORD_RE = re.compile(r"тест", re.IGNORECASE)

# --- блоки машинно-читаемых фактов (фаза 4) -------------------------------
# Дефект, измеренный tests/probe_check_gap.py: сверка жила на одной
# markdown-таблице и числе тестов. Всё, что отчёт утверждает ТЕКСТОМ
# (84 кросс-файловых дубля, 100 оставшихся, 190 на входе, provenance-факты),
# не сверялось ни с чем: подмена 84→7 и 100→77 давала ok=True. Поэтому
# числа вне маркера текстом числом не считаются — сверяются только факты,
# помеченные строкой `<!-- p1-fact: ключ = значение -->`.
_FACT_RE = re.compile(
    r"^<!--\s*p1-fact:\s*(?P<key>[a-z0-9_]+)\s*=\s*(?P<value>[^\s>]+)\s*-->$",
    re.MULTILINE,
)
_FACT_BLOCK_OPEN = "<!-- p1-facts:start -->"
_FACT_BLOCK_CLOSE = "<!-- p1-facts:end -->"


def parse_facts(text: str) -> Dict[str, str]:
    """Все объявленные факты отчёта: {ключ: значение как есть}.

    Ключи не повторяются: второе объявление того же ключа — признак
    порчи отчёта, и `duplicate_fact_keys` его отдельно считает.
    """
    facts: Dict[str, str] = {}
    for match in _FACT_RE.finditer(text):
        facts[match.group("key")] = match.group("value")
    return facts


def duplicate_fact_keys(text: str) -> List[str]:
    """Ключи, объявленные в отчёте больше одного раза."""
    seen: List[str] = []
    for match in _FACT_RE.finditer(text):
        key = match.group("key")
        if key in seen:
            continue
        seen.append(key)
    counts = {k: 0 for k in seen}
    for match in _FACT_RE.finditer(text):
        counts[match.group("key")] += 1
    return sorted(k for k, n in counts.items() if n > 1)


#: Ключи фактов, которые сверка умеет вычислить из живых данных. Ключ, которого
#: нет в этом списке, в отчёте считается опечаткой (неизвестный факт).
FACT_BUILDERS: Dict[str, str] = {
    "files": "число memory-файлов",
    "insights_total": "всего инсайтов на входе",
    "junk": "мусорных записей",
    "duplicates_inside": "дублей внутри одного файла",
    "kept": "чистых записей (после фильтрации мусора)",
    "schema_problems": "проблем схемы",
    "cross_file_duplicates": "кросс-файловых дублей (dedupe --scope all)",
    "cross_kept": "сколько записей остаётся после глобальной дедупликации",
    "prov_total": "provenance: всего инсайтов",
    "prov_clean": "provenance: чистых",
    "prov_no_tags": "provenance: записей без тегов",
    "prov_no_source_url": "provenance: записей без source_url",
    "prov_no_timestamp": "provenance: записей без timestamp",
    "prov_relevance_values": "provenance: число различных значений relevance_score",
    "ap_unique_sets": "provenance: число различных наборов applicable_projects",
    "ap_uniform_all_projects": "provenance: записей с applicable_projects = [1,2,3,4]",
    "ap_discriminates": "provenance: 1, если applicable_projects различает проекты",
    "tests": "число тестов, собираемых в tests/ (то же, что сверяет count_tests)",
}


def live_facts(root: Path, tests: Optional[int] = None) -> Dict[str, int]:
    """Живые числа, которые обязан совпадать блок фактов отчёта.

    Считаются ровно те же величины, что печатают `report`, `dedupe --scope all`
    и `provenance`, — сверка идёт с теми же прогонами, а не с отдельной логикой.
    """
    from .crossfile import plan_crossfile
    from .provenance import audit

    root = Path(root)
    if tests is None:
        tests = count_tests(root)
    files = list(iter_memory_files(root))
    docs = [load(f) for f in files]
    rows = [summarize(d) for d in docs]
    _, stats = plan_crossfile(list(zip(files, docs)))
    prov = audit(root, project=1)
    ap = prov["applicable_projects"]
    facts = {
        "files": len(files),
        "insights_total": sum(r["raw"]["input"] for r in rows),
        "junk": sum(r["raw"]["junk"] for r in rows),
        "duplicates_inside": sum(r["raw"]["duplicates"] for r in rows),
        "kept": sum(r["raw"]["kept"] for r in rows),
        "schema_problems": sum(len(r["problems"]) for r in rows),
        "cross_file_duplicates": stats["cross_file_duplicates"],
        "cross_kept": stats["kept"],
        "prov_total": prov["total"],
        "prov_clean": prov["clean"],
        "prov_no_tags": prov["no_tags"],
        "prov_no_source_url": prov["no_source_url"],
        "prov_no_timestamp": prov["no_timestamp"],
        "prov_relevance_values": len(prov["relevance_score"]),
        "ap_unique_sets": ap["unique_sets"],
        "ap_uniform_all_projects": ap["uniform_all_projects"],
        "ap_discriminates": 1 if ap["discriminates"] else 0,
    }
    # Факт `tests` заявляем только когда есть чем мерить: без tests/ число
    # неизвестно, и его отсутствие в блоке — правда, а не дыра.
    if tests is not None:
        facts["tests"] = tests
    return facts


def fact_block(facts: Dict[str, int]) -> str:
    """Отрисовать блок фактов в каноническом порядке."""
    lines = [_FACT_BLOCK_OPEN]
    lines.extend(
        f"<!-- p1-fact: {key} = {facts[key]} -->" for key in FACT_BUILDERS if key in facts
    )
    lines.append(_FACT_BLOCK_CLOSE)
    return "\n".join(lines)


#: Каноническая фраза отчёта о числе тестов. Число тестов — единственное
#: утверждение отчёта, которое жило ТОЛЬКО текстом: блок фактов его не знал,
#: поэтому `stamp` не мог его починить, а сам `stamp` CLI рекомендовал как
#: ремонт. Найдено пробой tests/probe_stamp_repair.py: после `stamp`
#: сверка оставалась ok=False. Теперь фраза тоже генерируется по прогону.
_TESTS_SENTENCE_RE = re.compile(
    r"^(?P<head>[^\n]*?)(?P<count>\d+)(?P<tail>\s+зелёных\.?\s*)$",
    re.MULTILINE | re.IGNORECASE,
)


def stamp_test_sentence(text: str, tests: int) -> str:
    """Обновить число тестов в канонической фразе отчёта.

    Строка, которая объявляет число тестов, опознаётся по хвосту
    «<число> зелёных»; остальной текст не трогается.
    """
    match = _TESTS_SENTENCE_RE.search(text)
    if not match:
        return text
    return text[: match.start()] + (
        f"{match.group('head')}{tests}{match.group('tail')}"
    ) + text[match.end():]


def stamp_table(text: str, rows: Dict[str, List[int]]) -> str:
    """Переписать markdown-таблицу отчёта по живым числам файлов.

    Найдено пробой tests/probe_freshness_gap.py: `stamp` правил блок фактов,
    но не таблицу — а сверка проверяет таблицу. Память испортилась (появилась
    191-я запись), `stamp` отработал exit 0, а `report --check` остался
    красным: рекомендация CLI «пересобери отчёт командой stamp» была
    неисполнима. Контракт: после stamp сверка обязана давать exit 0.

    Правила, чтобы не испортить чужой текст:
      * переписываются ТОЛЬКО строки, уже распознанные `parse_report_table`;
      * новый файл в памяти, которого в таблице нет, ДОБАВЛЯЕТСЯ строкой
        перед строкой ИТОГО (иначе сверка ругается на files_missing_in_report);
      * строка ИТОГО пересчитывается как сумма живых строк;
      * формат жирных ячеек ИТОГО сохраняется.
    """
    per_file, total = parse_report_table(text)
    if not per_file and total is None:
        return text

    lines = text.splitlines()
    out: List[str] = []
    total_line: Optional[str] = None
    total_at: Optional[int] = None

    def render(name: str, numbers: List[int], bold: bool) -> str:
        cells = [name] + [str(n) for n in numbers]
        if bold:
            cells = [f"**{c}**" for c in cells]
        return "| " + " | ".join(cells) + " |"

    def total_row() -> str:
        if rows:
            nums = [sum(v[i] for v in rows.values()) for i in range(4)]
        elif per_file:
            nums = [sum(v[i] for v in per_file.values()) for i in range(4)]
        else:
            nums = total or [0, 0, 0, 0]
        return render("ИТОГО", nums, bold=total is not None)

    inserted = False
    for line in lines:
        match = _ROW_RE.match(line)
        if not match:
            out.append(line)
            continue
        cells = [_clean_cell(c) for c in match.group(1).split("|")]
        if len(cells) < 5:
            out.append(line)
            continue
        name = cells[0]
        try:
            [int(cells[i]) for i in range(1, 5)]
        except ValueError:
            out.append(line)
            continue
        if _TOTAL_RE.search(name):
            # Запоминаем ПОЗИЦИЮ строки ИТОГО, а не её текст: пересчитанную
            # строку нужно вернуть на место, а не в хвост документа.
            total_line = line
            total_at = len(out)
            continue
        if not name.endswith(".json"):
            out.append(line)
            continue
        if name in rows:
            out.append(render(name, rows[name], bold=False))
            continue
        # Файл из отчёта, которого больше нет в памяти: строку убираем —
        # иначе сверка вечно ругается на files_unknown_to_report.
        if name not in rows and name in per_file:
            continue
        out.append(line)

    # Вставляем недостающие строки файлов перед строкой ИТОГО.
    missing = [name for name in rows if name not in per_file]
    if total_at is None:
        # ИТОГО в отчёте не было — ставим её (и недостающие строки файлов)
        # сразу после последней строки таблицы, а не в хвост документа.
        last = max(
            (
                i
                for i, l in enumerate(out)
                if _ROW_RE.match(l)
                and l.rstrip().endswith("|")
                and ".json" in _clean_cell(l.strip().strip("|").split("|")[0])
            ),
            default=len(out) - 1,
        )
        total_at = last + 1
    for offset, name in enumerate(missing):
        out.insert((total_at or 0) + offset, render(name, rows[name], bold=False))
    if missing:
        total_at = (total_at or 0) + len(missing)
        inserted = True

    # Строка ИТОГО: на прежнем месте, если она была, иначе после таблицы.
    # Если строки не было вовсе — её нужно дописать, даже когда вставлялись
    # строки файлов: иначе таблица остаётся без итога.
    if total_at is not None:
        # Числа не поменялись — сохраняем исходную строку байт в байт:
        # жирность и оформление чужого отчёта не наше дело.
        out.insert(total_at, total_line or total_row())
    else:
        out.append(total_row())
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def stamp_report(
    text: str,
    facts: Dict[str, int],
    rows: Optional[Dict[str, List[int]]] = None,
) -> str:
    """Полный ремонт отчёта по прогону: блок фактов, число тестов и таблица.

    Контракт, который проверяют tests/probe_stamp_repair.py и
    tests/probe_freshness_gap.py: после `stamp` команда `report --check`
    обязана дать exit 0. Всё, что сверка умеет проверять, stamp обязан
    уметь чинить.
    """
    stamped = stamp_facts(text, facts)
    if "tests" in facts:
        stamped = stamp_test_sentence(stamped, facts["tests"])
    if rows is not None:
        stamped = stamp_table(stamped, rows)
    return stamped


def stamp_facts(text: str, facts: Dict[str, int]) -> str:
    """Заменить ТОЛЬКО блок фактов, остальной текст не трогая.

    Если блока нет — он дописывается в конец отчёта. Возвращает новый текст;
    запись на диск делает вызывающий (атомарно, с .bak).
    """
    block = fact_block(facts)
    if _FACT_BLOCK_OPEN in text and _FACT_BLOCK_CLOSE in text:
        head, _, rest = text.partition(_FACT_BLOCK_OPEN)
        _, _, tail = rest.partition(_FACT_BLOCK_CLOSE)
        return head + block + tail
    separator = "" if text.endswith("\n") else "\n"
    return f"{text}{separator}\n{block}\n"


def write_text_atomic(path: Path, text: str, backup: bool = True) -> Path:
    """Атомарно перезаписать текстовый файл: write-to-tmp + os.replace + .bak.

    Отдельная функция, а не `loader.save_atomic`: тот пишет JSON-объект,
    а отчёт качества памяти — markdown.
    """
    import os
    import shutil
    import tempfile

    path = Path(path)
    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def _clean_cell(cell: str) -> str:
    return cell.replace("*", "").strip()


def parse_report_table(text: str) -> Tuple[Dict[str, List[int]], Optional[List[int]]]:
    """Достать из markdown-отчёта числа по файлам и итоговую строку.

    Возвращает ({имя файла: [всего, мусор, дубли, чистых]}, итог или None).
    Строки, которые не являются таблицей, игнорируются; строка ИТОГО
    отделяется от построчных, чтобы её можно было сверять отдельно.
    """
    per_file: Dict[str, List[int]] = {}
    total: Optional[List[int]] = None
    for line in text.splitlines():
        match = _ROW_RE.match(line)
        if not match:
            continue
        cells = [_clean_cell(c) for c in match.group(1).split("|")]
        if len(cells) < 5:
            continue
        name = cells[0]
        try:
            numbers = [int(cells[i]) for i in range(1, 5)]
        except ValueError:
            continue
        if _TOTAL_RE.search(name):
            total = numbers
        elif name.endswith(".json"):
            per_file[name] = numbers
    return per_file, total


def _purge_foreign_test_modules(tests_dir: Path) -> None:
    """Выкинуть из sys.modules тестовые модули из ЧУЖОГО каталога.

    unittest-поиск импортирует `test_*.py` как модули верхнего уровня и
    кладёт их в sys.modules. Из-за этого вторая копия проекта в том же
    процессе (сборки проб и тестов в tmp) даёт ImportError «module
    incorrectly imported», `count_tests` глотает исключение и возвращает 0 —
    то есть сверка числа тестов молча выдаёт ложное расхождение. Найдено
    пробой фаз 3–4; лечится точечно, глобальный sys.modules не чистится.
    """
    import sys

    resolved = str(tests_dir.resolve())
    for name, module in list(sys.modules.items()):
        if name == "tests" or not name.startswith("test"):
            continue
        origin = getattr(module, "__file__", None) or ""
        if origin and not origin.startswith(resolved):
            del sys.modules[name]


def count_tests(root: Path) -> Optional[int]:
    """Сколько тестов реально собирается в tests/ (без их выполнения).

    Обнаруживает устаревшие заявления вида «49 зелёных тестов» прямо в тексте
    отчёта, не требуя запускать тесты из самого отчёта.

    Возвращает None, если каталога tests/ нет вовсе: это «нечем проверять»,
    а не «ноль тестов». Ноль означал бы, что отчёт с числом тестов заведомо
    врёт, и подменял бы перенос отчёта ложным красным расхождением.
    """
    tests_dir = Path(root) / "tests"
    if not tests_dir.is_dir():
        return None
    _purge_foreign_test_modules(tests_dir)
    try:
        return unittest.defaultTestLoader.discover(
            str(tests_dir), pattern="test*.py", top_level_dir=str(tests_dir)
        ).countTestCases()
    except Exception:  # noqa: BLE001 — отчёт не должен падать из-за тестов
        return 0


def declared_tests(text: str) -> List[int]:
    """Все числа, которыми отчёт заявляет о количестве тестов.

    Ловит обе формы записи: «49 зелёных тестов» (число перед словом) и
    «тесты `tests/test_p1_memory.py` — 49 зелёных» (число после). Вторая
    форма раньше проскакивала молча, и сверка отчёта отдавала exit 0.
    """
    found = {int(m.group(1)) for m in _TESTS_RE.finditer(text)}
    for line in text.splitlines():
        if not _TEST_WORD_RE.search(line):
            continue
        for match in _COUNTED_RE.finditer(line):
            found.add(int(match.group(1)))
    return sorted(found)


def expected_rows(root: Path) -> Dict[str, List[int]]:
    """Живые числа по каждому memory-файлу в том же порядке, что и отчёт."""
    memory_dir = Path(root) / "memory"
    rows: Dict[str, List[int]] = {}
    if not memory_dir.is_dir():
        return rows
    for path in sorted(memory_dir.glob("professor_insights_cycle_*.json")):
        summary = summarize(load(path))
        raw = summary["raw"]
        rows[path.name] = [raw["input"], raw["junk"], raw["duplicates"], raw["kept"]]
    return rows


def check_report(root: Path, report_name: str = DEFAULT_REPORT) -> Dict[str, Any]:
    """Сверить MEMORY_REPORT.md с прогоном. Ничего не пишет."""
    root = Path(root)
    report_path = root / report_name
    tests_live = count_tests(root)
    facts_live = live_facts(root, tests=tests_live)
    result: Dict[str, Any] = {
        "report": str(report_path),
        "exists": report_path.exists(),
        "files_checked": 0,
        "files_missing_in_report": [],
        "files_unknown_to_report": [],
        "row_mismatches": [],
        "total_mismatches": [],
        "test_count_mismatches": [],
        "fact_mismatches": [],
        "facts_unknown": [],
        "facts_duplicated": [],
        "facts_missing": [],
        "facts_on_disk": facts_live,
        "tests_on_disk": tests_live,
        "ok": False,
    }
    if not report_path.exists():
        return result

    text = report_path.read_text(encoding="utf-8")
    per_file, total = parse_report_table(text)
    rows_live = expected_rows(root)

    result["files_missing_in_report"] = sorted(set(rows_live) - set(per_file))
    result["files_unknown_to_report"] = sorted(set(per_file) - set(rows_live))

    for name in sorted(set(rows_live) & set(per_file)):
        result["files_checked"] += 1
        if rows_live[name] != per_file[name]:
            result["row_mismatches"].append({
                "file": name,
                "report": per_file[name],
                "live": rows_live[name],
            })

    if total is not None:
        live_total = [
            sum(v[i] for v in rows_live.values()) for i in range(4)
        ] if rows_live else [0, 0, 0, 0]
        if live_total != total:
            result["total_mismatches"].append({"report": total, "live": live_total})
    else:
        result["total_mismatches"].append({"report": None, "live": "строка ИТОГО не найдена"})

    # Без каталога tests/ число тестов неизвестно: сверять нечего, и падать
    # на этом нельзя — иначе перенос отчёта в голый каталог всегда красный.
    if tests_live is not None:
        for declared in declared_tests(text):
            if declared != tests_live:
                result["test_count_mismatches"].append(
                    {"report": declared, "live": tests_live}
                )

    # --- блок машинно-читаемых фактов (фаза 4) --------------------------
    declared_facts = parse_facts(text)
    result["facts_unknown"] = sorted(k for k in declared_facts if k not in FACT_BUILDERS)
    result["facts_duplicated"] = duplicate_fact_keys(text)
    for key, value in sorted(declared_facts.items()):
        if key not in FACT_BUILDERS:
            continue
        expected = facts_live.get(key)
        if expected is None:
            continue
        if str(expected) != value:
            result["fact_mismatches"].append(
                {"fact": key, "report": value, "live": expected}
            )
    # Факт `tests` не считаем пропавшим, если измерять нечего (нет tests/).
    result["facts_missing"] = sorted(
        k
        for k in FACT_BUILDERS
        if k not in declared_facts and (k != "tests" or tests_live is not None)
    )

    result["ok"] = not (
        result["files_missing_in_report"]
        or result["files_unknown_to_report"]
        or result["row_mismatches"]
        or result["total_mismatches"]
        or result["test_count_mismatches"]
        or result["fact_mismatches"]
        or result["facts_unknown"]
        or result["facts_duplicated"]
        or result["facts_missing"]
    )
    return result
