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
from .identity import distinguish, identity_report
from .loader import DEFAULT_DIR, MemoryInvalid, load as load_one, validate_corpus
from .metrics import metrics as compute_metrics, search
from .paths import PathRefused, append_section, project_root
from .report import build_report, write_report

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
        from .paths import safe_path

        target = safe_path(args.file) if args.file else project_root() / "CHRONICLE.md"
    except PathRefused as exc:
        print(f"отказ: {exc}", file=sys.stderr)
        return EXIT_USAGE
    body = args.body or "\n".join(line.lstrip("- ") for line in (args.lines or []))
    appended = append_section(target, args.title, body, backup=not args.no_backup)
    backup_note = "" if args.no_backup else " (с бэкапом)"
    print(("записано" if appended else "раздел уже есть — ничего не менялось")
          + backup_note)
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
    sub = parser.add_subparsers(dest="command", parser_class=argparse.ArgumentParser)

    sub.add_parser("validate", parents=[common],
                   help="проверить схему всех memory-файлов")
    sub.add_parser("identity", parents=[common],
                   help="сравнить тело Project3 с соседними проектами")
    sub.add_parser("distinct", parents=[common],
                   help="записи, которых нет ни у соседей")
    sub.add_parser("audit", parents=[common],
                   help="аудит адресации applicable_projects")
    sub.add_parser("metrics", parents=[common], help="метрики корпуса")

    p_load = sub.add_parser("load", parents=[common],
                            help="прочитать один memory-файл")
    p_load.add_argument("path")

    p_search = sub.add_parser("search", parents=[common], help="поиск по корпусу")
    p_search.add_argument("query", nargs="?")
    p_search.add_argument("--category")
    p_search.add_argument("--source-type")
    p_search.add_argument("--min-score", type=float)

    p_report = sub.add_parser("report", parents=[common],
                              help="собрать DUPLICITY_REPORT.md")
    p_report.add_argument("--fix", action="store_true", help="записать файл")
    p_report.add_argument("--out", help="путь внутри проекта")

    p_canon = sub.add_parser("canon", parents=[common], help="канонический корпус")
    p_canon.add_argument("--fix", action="store_true", help="записать файл")
    p_canon.add_argument("--out", help="путь внутри проекта")

    p_chron = sub.add_parser("chronicle", parents=[common],
                             help="дописать раздел в CHRONICLE.md")
    p_chron.add_argument("--title", required=True)
    p_chron.add_argument("--body")
    p_chron.add_argument("--line", dest="lines", action="append")
    p_chron.add_argument("--file", help="файл внутри проекта вместо CHRONICLE.md")
    p_chron.add_argument("--no-backup", action="store_true")

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