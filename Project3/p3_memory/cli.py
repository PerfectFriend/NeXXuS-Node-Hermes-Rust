"""CLI Project3: python3 -m p3_memory <команда> (пункт 8 плана).

Команды: validate, load, identity, audit, metrics, search, report, canon,
chronicle. Ничего не пишет на диск без явного `--fix`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

from .attribution import addressing_from_disk
from .canon import corpus, save_canon
from .gate import (
    build_facts, claim_from_facts, facts_digest, gate_check, honesty_probe,
    read_registry, registry_by_status, registry_entries,
)
from .diff import cycle_coverage, diff, diff_text
from .identity import distinguish, identity_report
from .loader import DEFAULT_DIR, MemoryInvalid, load as load_one, validate_corpus
from .metrics import metrics as compute_metrics, search
from .paths import PathRefused, append_section, project_root
from .report import build_report, check_report, write_report

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def _out(data: Any, as_json: bool, human: str = "") -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif human:
        print(human)


def _memory_dir(args) -> Path:
    return Path(args.memory_dir) if args.memory_dir else DEFAULT_DIR


def cmd_validate(args) -> int:
    result = validate_corpus(_memory_dir(args))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK if result["valid"] else EXIT_FAIL
    print(f"файлов: {result['files']}, записей: {result['records']}, "
          f"претензий: {result['problem_count']}")
    for problem in result["problems"][: args.limit]:
        print("  " + problem)
    if len(result["problems"]) > args.limit:
        print(f"  … ещё {len(result['problems']) - args.limit}")
    return EXIT_OK if result["valid"] else EXIT_FAIL


def cmd_load(args) -> int:
    try:
        data = load_one(args.path)
    except MemoryInvalid as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return EXIT_FAIL
    _out(
        {
            "file": data.get("_source_file"),
            "cycle": data.get("cycle"),
            "project": data.get("project"),
            "total_insights": data.get("total_insights"),
            "markers_removed": data.get("_markers_removed"),
        },
        args.as_json,
        f'файл {data.get("_source_file")}: цикл {data.get("cycle")}, '
        f'записей {data.get("total_insights")}, '
        f'снято маркеров {len(data.get("_markers_removed") or [])}',
    )
    return EXIT_OK


def cmd_identity(args) -> int:
    result = identity_report(_memory_dir(args))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(f"Project3: {result['own_records']} записей, "
          f"хэш содержания {result['own_hash']}, "
          f"хэш байтов {result['own_byte_hash']}")
    for name, res in result["per_sibling"].items():
        if "error" in res:
            print(f"  {name}: ошибка — {res['error']}")
            continue
        if res["identical"]:
            verdict = "идентичен по содержанию"
        else:
            verdict = "отличается"
        bytes_note = "байты равны" if res["byte_identical"] else "байты НЕ равны"
        overlay = res.get("service_overlay") or {}
        if not res["byte_identical"] and overlay.get("fields"):
            fields = ", ".join(f"{k}×{v}" for k, v in overlay["fields"].items())
            bytes_note += f" (служебная надстройка соседа: {fields})"
        print(f"  {name}: {verdict}, {bytes_note}, "
              f"общих ключей {res['shared_keys']}/{res['own_keys']}, "
              f"Жаккар {res['jaccard']}")
        div = res.get("divergence")
        if div:
            for field, count in list(div["fields"].items())[: args.limit]:
                print(f"      различается поле {field}: {count} записей")
    print(f"все соседи идентичны по содержанию: "
          f"{'да' if result['all_identical'] else 'нет'}; "
          f"байт в байт: {', '.join(result['byte_identical_siblings']) or 'никто'}; "
          f"собственных ключей: {result['distinct_keys']}")
    return EXIT_OK


def cmd_distinct(args) -> int:
    rows = distinguish(_memory_dir(args))
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK
    if not rows:
        print("собственных записей нет: Project3 полностью совпадает с соседями")
        return EXIT_OK
    print(f"собственных записей: {len(rows)}")
    for row in rows[: args.limit]:
        print(f"  {row['topic']} ({row['category']})")
    return EXIT_OK


def cmd_audit(args) -> int:
    result = addressing_from_disk(_memory_dir(args))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(f"записей: {result['total']}, дефолтных: {result['default_addressed']} "
          f"(доля {result['default_ratio']:.4f})")
    print(f"фильтр способен отсечь: {'да' if result['filter_works'] else 'нет'}")
    print(result["verdict"])
    return EXIT_OK


def cmd_metrics(args) -> int:
    result = compute_metrics(_memory_dir(args))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    for key in ("files", "records_input", "records_total", "duplicates_removed",
                "junk_topics", "score_mean", "attribution_own",
                "attribution_shared", "attribution_unattributed"):
        print(f"{key}: {result[key]}")
    return EXIT_OK


def cmd_search(args) -> int:
    rows = search(
        args.query or "",
        memory_dir=_memory_dir(args),
        category=args.category,
        source_type=args.source_type,
        min_score=args.min_score,
        limit=args.limit,
    )
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK
    if not rows:
        print("ничего не найдено")
        return EXIT_OK
    for row in rows:
        print(f"[{row['rank']}] {row['topic']} ({row['category']}) "
              f"rel={row['relevance']} ×{row['occurrences']}")
    return EXIT_OK


def cmd_report(args) -> int:
    if args.check:
        result = check_report(
            Path(args.out) if args.out else None,
            memory_dir=_memory_dir(args),
        )
        if args.as_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result["ok"]:
            print(f"отчёт свежий: {result['path']} совпадает с build_report()")
        else:
            print(f"отчёт устарел: {result['path']}")
            for line in result["missing_lines"][: args.limit]:
                print(f"  [нет в файле] {line}")
            for line in result["extra_lines"][: args.limit]:
                print(f"  [лишнее в файле] {line}")
            print("починить: p3_memory report --fix")
        return EXIT_OK if result["ok"] else EXIT_FAIL
    if not args.fix:
        print(build_report(_memory_dir(args)))
        return EXIT_OK
    try:
        from .paths import safe_path

        target = safe_path(args.out) if args.out else None
        backup = write_report(target, memory_dir=_memory_dir(args), fix=True)
    except PathRefused as exc:
        print(f"отказ: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"отчёт записан{(f', бэкап: {backup.name}' if backup else '')}")
    return EXIT_OK


def cmd_canon(args) -> int:
    canon_result = corpus(_memory_dir(args))
    if not args.fix:
        print(json.dumps(
            {
                "files": canon_result["files"],
                "records_input": canon_result["total_input"],
                "unique": canon_result["unique"],
                "duplicates_removed": canon_result["duplicates_removed"],
            },
            ensure_ascii=False,
            indent=2,
        ))
        return EXIT_OK
    try:
        from .paths import safe_path

        target = safe_path(args.out or "CANON.json")
        backup = save_canon(canon_result, target, fix=True)
    except PathRefused as exc:
        print(f"отказ: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"канонический корпус записан в {target.name}"
          f"({canon_result['unique']} записей){f', бэкап: {backup.name}' if backup else ''}")
    return EXIT_OK


def cmd_chronicle(args) -> int:
    try:
        from .paths import check_chronicle, safe_path

        target = safe_path(args.file) if args.file else project_root() / "CHRONICLE.md"
    except PathRefused as exc:
        print(f"отказ: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.check:
        result = check_chronicle(target)
        if args.as_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result["ok"]:
            print(f"хроника чиста: {result['path']} "
                  f"({len(result['headings'])} разделов)")
        else:
            print(f"претензии к хронике: {result['path']}")
            for problem in result["problems"]:
                print(f"  - {problem}")
        return EXIT_OK if result["ok"] else EXIT_FAIL
    if not args.check and not args.title:
        print("ошибка: нужен --title (или --check для аудита)",
              file=sys.stderr)
        return EXIT_USAGE
    body = args.body or "\n".join(line.lstrip("- ") for line in (args.lines or []))
    appended = append_section(target, args.title, body, backup=not args.no_backup)
    backup_note = "" if args.no_backup else " (с бэкапом)"
    print(("записано" if appended else "раздел уже есть — ничего не менялось")
          + backup_note)
    return EXIT_OK


def cmd_gate(args) -> int:
    """Печать машинных фактов и (по --claim) их сверка живым гейтом.

    По умолчанию печатается JSON фактов — это то, что гейт принимает на
    вход. С `--claim` сверяется заявление агента и возвращается код гейта:
    0 — подтверждено, 2 — расхождение.
    """
    facts = build_facts(target=args.target, run=not args.no_run)
    if args.write:
        try:
            from .paths import safe_path

            safe_path(args.write)
        except PathRefused as exc:
            print(f"отказ: {exc}", file=sys.stderr)
            return EXIT_USAGE
    if args.claim:
        try:
            claim = json.loads(args.claim)
        except json.JSONDecodeError as exc:
            print(f"заявление не разобрано: {exc}", file=sys.stderr)
            return EXIT_USAGE
        problems = gate_check(facts, claim)
        print(json.dumps(
            {"facts_digest": facts_digest(facts), "problems": problems,
             "exit": 0 if not problems else 2},
            ensure_ascii=False, indent=2))
        if args.write:
            _write_case(args.write, {"name": args.name, "claim": claim,
                                     "facts": facts})
        return 0 if not problems else 2
    if args.write:
        _write_case(args.write, {"name": args.name,
                                 "claim": claim_from_facts(facts),
                                 "facts": facts})
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    return EXIT_OK


def _write_case(relative: str, case: dict) -> None:
    from .paths import atomic_write, safe_path

    target = safe_path(relative)
    atomic_write(target, json.dumps(case, ensure_ascii=False, indent=2) + "\n",
                 backup=False)
    print(f"кейс записан в {target.name}")


def cmd_honesty(args) -> int:
    """Сквозная проверка честности (пункт 20).

    Три кейса: честное заявление по фактам, завышенное на 1 тест, и молчащее
    «цикл закрыт» без единого числа. Код 0 — все кейсы сработали как
    предписано; 2 — проверка не сработала, то есть система перестала ловить
    ложное утверждение.
    """
    result = honesty_probe(target=args.target, run=not args.no_run)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"факты: {result['facts_digest']}")
        for name, case in result["cases"].items():
            verdict = "пойман" if case["problems"] else "пропущен"
            expect = "должен падать" if case["should_fail"] else "должен пройти"
            print(f"  {name}: {verdict} (код {case['gate_exit']}, {expect})")
            for problem in case["problems"]:
                print(f"      - {problem}")
        print(f"итог: {result['verdict']}")
    return EXIT_OK if result["passed"] else EXIT_FAIL


def cmd_registry(args) -> int:
    """Показать реестр дефектов и его согласованность.

    `--json` печатает ТОЛЬКО JSON: смешивание человеческого текста и JSON в
    одном потоке ломает разбор вывода потребителем (тест поймал это на
    живом прогоне, а не на чтении кода).
    """
    reg = read_registry(project_root())
    if args.as_json:
        payload = {
            "counters": reg,
            "by_status": (registry_by_status(project_root())
                          if reg is not None and "error" not in reg else {}),
            "entries": (registry_entries(project_root())
                        if reg is not None and "error" not in reg else []),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK if reg is not None and "error" not in reg else EXIT_FAIL
    if reg is None:
        print("реестра дефектов нет")
        return EXIT_FAIL
    if "error" in reg:
        print(f"реестр не разобран: {reg['error']}")
        return EXIT_FAIL
    counts = registry_by_status(project_root())
    print(f"всего {reg['total']}, открыто {reg['open']}, закрыто {reg['closed']}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    for entry in registry_entries(project_root()):
        marker = "OPEN " if entry.get("status") in ("open", "new", "wip", "todo") else "CLOSED"
        print(f"  [{marker}] {entry.get('id')}: {entry.get('title')}")
    return EXIT_OK


def cmd_cycles(args) -> int:
    result = cycle_coverage(_memory_dir(args))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    if not result["cycles"]:
        print("циклов не найдено")
        return EXIT_OK
    for entry in result["cycles"]:
        print(f"цикл {entry['file_cycle']}: {entry['file']} — "
              f"{entry['records']} записей")
    if result["numbering_gaps"]:
        gaps = ", ".join(f"{lo}–{hi}" for lo, hi in result["numbering_gaps"])
        print(f"разрывы нумерации: {gaps}")
    else:
        print("разрывов нумерации нет")
    for delta in result["record_deltas"]:
        sign = "+" if delta["records_delta"] >= 0 else ""
        print(f"{delta['from']} → {delta['to']}: {sign}{delta['records_delta']} "
              f"записей")
    return EXIT_OK


def cmd_diff(args) -> int:
    result = diff(
        _memory_dir(args), args.ref_from, args.ref_to,
    )
    _out(result, args.as_json, diff_text(result, args.limit))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="p3_memory",
        description="Project3 — память Профессора: загрузка, канонизация, аудит",
    )
    # Общие опции разрешены до и после имени команды — argparse сам по себе
    # принимает их только слева, а в CLI писать `--memory-dir` после команды
    # естественнее, поэтому продублированы в общий родительский парсер.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--memory-dir", help="каталог memory (по умолчанию ./memory)")
    common.add_argument("--json", dest="as_json", action="store_true",
                        help="вывод в JSON")
    common.add_argument("--limit", type=int, default=20, help="сколько строк печатать")
    parser = argparse.ArgumentParser(
        prog="p3_memory",
        description="Project3 — память Профессора: загрузка, канонизация, аудит",
        parents=[common],
    )
    # Подпарсер получает КОПИЮ общих опций, и его значения по умолчанию
    # затирают разобранные главным парсером: `--json metrics` молча печатал
    # человеческий текст вместо JSON. `argparse.SUPPRESS` как default не даёт
    # подпарсеру ничего записать, поэтому побеждает явно заданное значение.
    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--memory-dir", default=argparse.SUPPRESS,
                            help="каталог memory (по умолчанию ./memory)")
    sub_common.add_argument("--json", dest="as_json",
                            action="store_true", default=argparse.SUPPRESS,
                            help="вывод в JSON")
    sub_common.add_argument("--limit", type=int, default=argparse.SUPPRESS,
                            help="сколько строк печатать")
    # Базы для значений, если опция не задана ни слева, ни справа.
    parser.set_defaults(as_json=False, memory_dir=None, limit=20)
    sub = parser.add_subparsers(dest="command", parser_class=argparse.ArgumentParser)

    sub.add_parser("validate", parents=[sub_common],
                   help="проверить схему всех memory-файлов")
    sub.add_parser("identity", parents=[sub_common],
                   help="сравнить тело Project3 с соседними проектами")
    sub.add_parser("distinct", parents=[sub_common],
                   help="записи, которых нет ни у соседей")
    sub.add_parser("audit", parents=[sub_common],
                   help="аудит адресации applicable_projects")
    sub.add_parser("metrics", parents=[sub_common], help="метрики корпуса")

    p_load = sub.add_parser("load", parents=[sub_common],
                            help="прочитать один memory-файл")
    p_load.add_argument("path")

    p_search = sub.add_parser("search", parents=[sub_common], help="поиск по корпусу")
    p_search.add_argument("query", nargs="?")
    p_search.add_argument("--category")
    p_search.add_argument("--source-type")
    p_search.add_argument("--min-score", type=float)

    p_report = sub.add_parser("report", parents=[sub_common],
                              help="собрать DUPLICITY_REPORT.md")
    p_report.add_argument("--fix", action="store_true", help="записать файл")
    p_report.add_argument("--check", action="store_true",
                          help="проверить свежесть артефакта (exit 0/1)")
    p_report.add_argument("--out", help="путь внутри проекта")

    p_canon = sub.add_parser("canon", parents=[sub_common], help="канонический корпус")
    p_canon.add_argument("--fix", action="store_true", help="записать файл")
    p_canon.add_argument("--out", help="путь внутри проекта")

    p_chron = sub.add_parser("chronicle", parents=[sub_common],
                             help="дописать раздел в CHRONICLE.md")
    p_chron.add_argument("--title")
    p_chron.add_argument("--body")
    p_chron.add_argument("--line", dest="lines", action="append")
    p_chron.add_argument("--file", help="файл внутри проекта вместо CHRONICLE.md")
    p_chron.add_argument("--no-backup", action="store_true")
    p_chron.add_argument("--check", action="store_true",
                         help="аудит файла (exit 0/1), ничего не пишет")

    p_gate = sub.add_parser("gate", parents=[sub_common],
                            help="машинные факты для tools/cycle_claim_gate.py")
    p_gate.add_argument("--claim", help="заявление агента JSON для сверки")
    p_gate.add_argument("--name", default="project3", help="имя кейса")
    p_gate.add_argument("--target", help="что гонять (например tests/)")
    p_gate.add_argument("--no-run", action="store_true",
                        help="не запускать прогон, а зафиксировать его отсутствие")
    p_gate.add_argument("--write", help="записать кейс в файл внутри проекта")

    sub.add_parser("registry", parents=[sub_common],
                   help="реестр дефектов Project3")

    p_honesty = sub.add_parser("honesty", parents=[sub_common],
                               help="сквозная проверка честности против гейта")
    p_honesty.add_argument("--target", help="что гонять (например tests/)")
    p_honesty.add_argument("--no-run", action="store_true",
                           help="не запускать прогон, а зафиксировать его отсутствие")

    sub.add_parser("cycles", parents=[sub_common],
                   help="покрытие циклов: файлы, записи, разрывы нумерации")
    p_diff = sub.add_parser("diff", parents=[sub_common],
                            help="дифф двух циклов (по умолчанию два последних)")
    p_diff.add_argument("ref_from", nargs="?",
                        help="число цикла или имя файла (по умолчанию предпоследний)")
    p_diff.add_argument("ref_to", nargs="?",
                        help="число цикла или имя файла (по умолчанию последний)")

    return parser


HANDLERS = {
    "validate": cmd_validate,
    "load": cmd_load,
    "identity": cmd_identity,
    "distinct": cmd_distinct,
    "audit": cmd_audit,
    "metrics": cmd_metrics,
    "search": cmd_search,
    "report": cmd_report,
    "canon": cmd_canon,
    "chronicle": cmd_chronicle,
    "gate": cmd_gate,
    "registry": cmd_registry,
    "honesty": cmd_honesty,
    "diff": cmd_diff,
    "cycles": cmd_cycles,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_USAGE
    handler = HANDLERS[args.command]
    try:
        return handler(args)
    except MemoryInvalid as exc:
        print(f"ошибка памяти: {exc}", file=sys.stderr)
        return EXIT_FAIL
    except PathRefused as exc:
        print(f"отказ: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())