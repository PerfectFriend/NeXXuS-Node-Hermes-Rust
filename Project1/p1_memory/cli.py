"""CLI Project1: report | validate | dedupe.

    python3 -m p1_memory report            # сводка по всей памяти
    python3 -m p1_memory report --json
    python3 -m p1_memory validate          # список проблем, exit 1 если есть
    python3 -m p1_memory dedupe --fix      # перезапись файлов (атомарно, с .bak)
    python3 -m p1_memory chronicle --title "..." --body "..."

По умолчанию ничего не пишется: --fix обязателен для записи.
Единственная команда, которая пишет сама по себе явному вызову, — chronicle
(запись в журнал проекта CHRONICLE.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import __version__
from .chronicle import CHRONICLE_NAME, append_entry, has_entry, now_stamp
from .crossfile import plan_crossfile
from .doctor import BLOCKING_KINDS, is_blocking, scan_tree, summarize as summarize_findings
from .freshness import (
    DEFAULT_REPORT,
    check_report,
    live_facts,
    parse_facts,
    stamp_facts,
    stamp_report,
    write_text_atomic,
)
from .loader import MemoryError_, iter_memory_files, load, save_atomic
from .provenance import audit as audit_provenance
from .validate import clean_insights, summarize, validate_document

DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def collect(root: Path, by_time: bool = False):
    files = iter_memory_files(root, by_time=by_time)
    return files, [load(f) for f in files]


def cmd_report(args) -> int:
    files, docs = collect(args.root, by_time=getattr(args, "by_time", False))
    if not files:
        print(f"Память не найдена: {args.root / 'memory'}")
        return 1

    rows = [summarize(d) for d in docs]
    totals = {
        "files": len(rows),
        "raw": sum(r["raw"]["input"] for r in rows),
        "junk": sum(r["raw"]["junk"] for r in rows),
        "duplicates": sum(r["raw"]["duplicates"] for r in rows),
        "kept": sum(r["raw"]["kept"] for r in rows),
        "problems": sum(len(r["problems"]) for r in rows),
    }

    if getattr(args, "check", False):
        return _report_check(args, totals)

    if args.json:
        print(json.dumps({"root": str(args.root), "version": __version__,
                          "totals": totals, "files": rows}, ensure_ascii=False, indent=2))
        return 0

    print(f"Project1 — сводка памяти (p1_memory {__version__})")
    print(f"каталог: {args.root / 'memory'}")
    for r in rows:
        name = Path(r["path"]).name
        markers = f", сняты маркеры {r['markers_removed']}" if r["markers_removed"] else ""
        print(f"  {name}: всего {r['raw']['input']}, мусор {r['raw']['junk']}, "
              f"дубли {r['raw']['duplicates']}, чистых {r['raw']['kept']}{markers}")
        for problem in r["problems"][:10]:
            print(f"      ! {problem}")
    print(f"ИТОГО: файлов {totals['files']}, инсайтов {totals['raw']}, "
          f"мусор {totals['junk']}, дубли {totals['duplicates']}, "
          f"чистых {totals['kept']}, проблем схемы {totals['problems']}")
    return 0


def _report_check(args, totals: dict) -> int:
    """Сверить MEMORY_REPORT.md с живым прогоном. Ничего не пишет."""
    report_name = getattr(args, "report", DEFAULT_REPORT)
    res = check_report(args.root, report_name)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 1

    if not res["exists"]:
        print(f"Отчёт не найден: {res['report']}")
        return 1
    print(f"Сверка отчёта: {res['report']}")
    print(f"  тестов на диске: {res['tests_on_disk']}")
    for name in res["files_missing_in_report"]:
        print(f"  ! файл есть в памяти, но нет в отчёте: {name}")
    for name in res["files_unknown_to_report"]:
        print(f"  ! файл есть в отчёте, но нет в памяти: {name}")
    for row in res["row_mismatches"]:
        print(f"  ! {row['file']}: в отчёте {row['report']}, в прогоне {row['live']}")
    for row in res["total_mismatches"]:
        print(f"  ! ИТОГО: в отчёте {row['report']}, в прогоне {row['live']}")
    for row in res["test_count_mismatches"]:
        print(f"  ! число тестов: в отчёте {row['report']}, на диске {row['live']}")
    for row in res["fact_mismatches"]:
        print(f"  ! факт {row['fact']}: в отчёте {row['report']}, в прогоне {row['live']}")
    for key in res["facts_unknown"]:
        print(f"  ! факт {key}: такого факта сверка не знает (опечатка в ключе?)")
    for key in res["facts_duplicated"]:
        print(f"  ! факт {key}: объявлен в отчёте больше одного раза")
    for key in res["facts_missing"]:
        print(f"  ! факт {key}: не объявлен в отчёте, хотя сверка его ждёт")
    if res["ok"]:
        print(f"Отчёт актуален: файлов {res['files_checked']}, расхождений нет.")
        return 0
    print("Отчёт устарел: пересобери MEMORY_REPORT.md (`python3 -m p1_memory stamp`).")
    return 1


def cmd_stamp(args) -> int:
    """Перезаписать блок машинно-читаемых фактов по живому прогону.

    Текст отчёта вне блока не трогается. Запись атомарная, с .bak.
    """
    report_name = getattr(args, "report", DEFAULT_REPORT)
    path = args.root / report_name
    if not path.exists():
        print(f"Отчёт не найден: {path}")
        return 1

    facts = live_facts(args.root)
    before = path.read_text(encoding="utf-8")
    after = stamp_report(before, facts)
    if after == before:
        print(f"Факты уже совпадают с прогоном: {report_name} не изменён.")
        return 0
    if getattr(args, "dry_run", False):
        print(f"[dry-run] {report_name}: {len(parse_facts(before))} → {len(facts)} фактов")
        for line in after.splitlines():
            if line.startswith("<!-- p1-fact:"):
                print(f"  {line}")
        return 0
    write_text_atomic(path, after, backup=True)
    print(f"Блок фактов обновлён: {report_name} (.bak сохранён)")
    for line in after.splitlines():
        if line.startswith("<!-- p1-fact:"):
            print(f"  {line}")
    return 0


def cmd_provenance(args) -> int:
    res = audit_provenance(args.root, project=args.project)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print(f"Project1 — происхождение памяти (проект {args.project})")
    print(f"  файлов: {res['files']}, всего инсайтов: {res['total']} "
          f"(мусор {res['junk']}, чистых {res['clean']})")
    print("  по типам источника:")
    for label, count in res["source_type"].items():
        print(f"    {label}: {count}")
    ap = res["applicable_projects"]
    print(f"  уникальных наборов applicable_projects: {ap['unique_sets']}")
    for label, count in ap["sets"].items():
        print(f"    {label}: {count}")
    print(f"  различает проекты: {'да' if ap['discriminates'] else 'НЕТ'}; "
          f"отбирается для проекта {args.project}: {ap['selects_for_project']}; "
          f"бесполезно для отбора: {ap['useless_for_selection']}")
    print(f"  значений relevance_score: {len(res['relevance_score'])} "
          f"({', '.join(f'{k}={v}' for k, v in sorted(res['relevance_score'].items()))})")
    print(f"  без тегов: {res['no_tags']}, без source_url: {res['no_source_url']}, "
          f"без timestamp: {res['no_timestamp']}")
    return 0


def cmd_validate(args) -> int:
    _, docs = collect(args.root)
    problems: List[str] = []
    for d in docs:
        problems.extend(validate_document(d))
    if args.json:
        print(json.dumps({"problems": problems, "count": len(problems)}, ensure_ascii=False, indent=2))
    elif problems:
        for p in problems:
            print(f"! {p}")
    else:
        print("Схема в порядке: проблем не найдено.")
    return 1 if problems else 0


def cmd_dedupe(args) -> int:
    files, docs = collect(args.root)
    scope = getattr(args, "scope", "file")
    pairs = list(zip(files, docs))

    if scope == "all":
        # Кросс-файловая очистка: один общий seen на все memory-файлы.
        plan, stats = plan_crossfile(pairs)
        changes = [(e["path"], e["doc"], e["kept"], e["stats"]) for e in plan]
    else:
        stats = {"files": len(pairs), "input": 0, "junk": 0,
                 "duplicates_inside": 0, "cross_file_duplicates": 0, "kept": 0}
        changes = []
        for path, doc in pairs:
            kept, st = clean_insights(doc["insights"])
            stats["input"] += st["input"]
            stats["junk"] += st["junk"]
            stats["duplicates_inside"] += st["duplicates"]
            stats["kept"] += st["kept"]
            if st["kept"] == st["input"]:
                continue
            changes.append((path, doc, kept, st))

    if args.json:
        payload = {
            "scope": scope,
            "dry_run": not args.fix,
            "totals": stats,
            "files": [
                {"file": Path(c[0]).name, "input": c[3]["input"], "junk": c[3]["junk"],
                 "duplicates_inside": c[3]["duplicates"],
                 "cross_file_duplicates": c[3].get("cross", 0),
                 "kept": c[3]["kept"],
                 "written": bool(args.fix)}
                for c in changes
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not args.fix:
            return 0

    marker = "FIX" if args.fix else "dry-run"
    for path, doc, kept, st in changes:
        print(f"[{marker}] {path.name}: {st['input']} → {st['kept']} "
              f"(мусор {st['junk']}, дубли внутри {st['duplicates']}, "
              f"кросс-файловые {st.get('cross', 0)})")
    if not changes:
        print("Чистить нечего: все файлы уже чистые.")
        return 0
    if not args.fix:
        print(f"Итого к очистке файлов: {len(changes)} (запусти с --fix)")
        return 0

    for path, doc, kept, st in changes:
        payload_doc = dict(doc)
        payload_doc["insights"] = kept
        payload_doc["total_insights"] = len(kept)
        save_atomic(path, payload_doc, backup=True)
        print(f"  записано: {path.name} ({len(kept)} записей), бэкап {path.name}.bak")
    return 0


def cmd_chronicle(args) -> int:
    """Дописать запись в CHRONICLE.md (атомарно, повтор по заголовку — no-op)."""
    path = args.root / args.file
    body = args.body
    if args.stats:
        _, docs = collect(args.root)
        rows = [summarize(d) for d in docs]
        lines = [
            f"- файлов: {len(rows)}",
            f"- инсайтов: {sum(r['raw']['input'] for r in rows)}",
            f"- мусор: {sum(r['raw']['junk'] for r in rows)}",
            f"- дубли: {sum(r['raw']['duplicates'] for r in rows)}",
            f"- чистых: {sum(r['raw']['kept'] for r in rows)}",
            f"- проблем схемы: {sum(len(r['problems']) for r in rows)}",
        ]
        body = (body + "\n" if body else "") + "\n".join(lines)

    stamp = args.stamp or now_stamp(datetime.now())
    if path.exists() and has_entry(path.read_text(encoding="utf-8"), args.title):
        print(f"Запись уже есть, пропускаю: {args.title}")
        return 0
    append_entry(path, args.title, body, stamp)
    print(f"Записано в {path.name}: {args.title} ({stamp})")
    return 0


def cmd_doctor(args) -> int:
    """Проверить целостность исходников проекта. exit 1, если найдена порча.

    По умолчанию печатаются только блокирующие находки: инструмент записи
    срезает завершающий перевод строки у всех файлов, поэтому без этого
    фильтра вывод всегда состоял бы из восьми предупреждений и сигнал
    порчи в нём тонул бы. Полный список — в --json или с --all.
    """
    findings = scan_tree(args.root)
    blocking = is_blocking(findings)
    shown = findings if args.all else [f for f in findings if f.kind in BLOCKING_KINDS]

    if args.json:
        print(json.dumps({
            "root": str(args.root),
            "blocking": blocking,
            "findings": [
                {"file": f.path, "kind": f.kind, "detail": f.detail,
                 "blocking": f.kind in BLOCKING_KINDS}
                for f in findings
            ],
            "summary": summarize_findings(findings),
        }, ensure_ascii=False, indent=2))
        return 1 if blocking else 0

    if not findings:
        print(f"Целостность в порядке: {args.root} (порчи нет)")
        return 0

    for f in shown:
        mark = "ПОРЧА" if f.kind in BLOCKING_KINDS else "внимание"
        print(f"[{mark}] {f}")

    counts = summarize_findings(findings)
    silent = len(findings) - len(shown)
    detail = ", ".join(f"{kind} — {n}" for kind, n in sorted(counts.items()))
    print(f"Находок: {len(findings)} ({detail})")
    if silent:
        print(f"Из них предупреждений без блокирующей силы: {silent} (показать: --all)")
    if blocking:
        print("Порча найдена: восстановление через `git checkout -- <путь>`.")
    return 1 if blocking else 0


def _split_prog(argv: Optional[List[str]]) -> List[str]:
    """Отбросить имя программы, если передан полный sys.argv.

    Удобно для вызовов из тестов и крон: main(["p1_memory", "report"]).
    """
    if argv and argv[0] and not argv[0].startswith("-") and "/" not in argv[0]:
        first = Path(argv[0]).name
        if first in ("p1_memory", "p1_memory.py", "__main__.py", "-m", "python3", "python"):
            return argv[1:]
    return list(argv) if argv else []


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = _split_prog(argv)
    parser = argparse.ArgumentParser(prog="p1_memory", description="Слой памяти Project1")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="корень проекта")
    parser.add_argument("--json", action="store_true", dest="json_global", help="вывод в JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="сводка по памяти")
    p_report.add_argument("--check", action="store_true",
                          help="сверить MEMORY_REPORT.md с прогоном (0 — совпало, 1 — расхождение)")
    p_report.add_argument("--report", default=DEFAULT_REPORT, help="имя файла отчёта")
    p_report.add_argument("--by-time", action="store_true",
                          help="порядок файлов по времени синхронизации (свежие первыми)")
    p_report.set_defaults(func=cmd_report)
    p_prov = sub.add_parser("provenance", help="аудит происхождения памяти (источники, applicable_projects)")
    p_prov.add_argument("--project", type=int, default=1, help="номер проекта для applicable_projects")
    p_prov.set_defaults(func=cmd_provenance)
    p_validate = sub.add_parser("validate", help="проверка схемы")
    p_validate.set_defaults(func=cmd_validate)
    p_dedupe = sub.add_parser("dedupe", help="дедупликация и фильтрация мусора")
    p_dedupe.add_argument("--fix", action="store_true", help="записать изменения (по умолчанию dry-run)")
    p_dedupe.add_argument("--scope", choices=("file", "all"), default="file",
                          help="file — внутри каждого файла (по умолчанию); "
                               "all — общий ключ по всем memory-файлам")
    p_dedupe.set_defaults(func=cmd_dedupe)

    p_chron = sub.add_parser("chronicle", help="дописать запись в журнал проекта")
    p_chron.add_argument("--title", required=True, help="заголовок записи (и защита от повтора)")
    p_chron.add_argument("--body", default="", help="текст записи")
    p_chron.add_argument("--file", default=CHRONICLE_NAME, help="имя файла журнала")
    p_chron.add_argument("--stamp", default="", help="метка времени (для тестов/кронов)")
    p_chron.add_argument("--stats", action="store_true", help="дописать сводку качества памяти")
    p_chron.set_defaults(func=cmd_chronicle)

    p_doctor = sub.add_parser("doctor", help="проверка целостности исходников (null-байты, мусор)")
    p_doctor.add_argument("--all", action="store_true", help="показать и предупреждения, не только порчу")
    p_doctor.set_defaults(func=cmd_doctor)

    p_stamp = sub.add_parser("stamp", help="перезаписать блок фактов MEMORY_REPORT.md по прогону")
    p_stamp.add_argument("--report", default=DEFAULT_REPORT, help="имя файла отчёта")
    p_stamp.add_argument("--dry-run", action="store_true", dest="dry_run",
                         help="показать, что изменится, ничего не писать")
    p_stamp.set_defaults(func=cmd_stamp)

    # --json разрешён и до, и после имени команды
    for sub_parser in (p_report, p_prov, p_validate, p_dedupe, p_chron, p_doctor, p_stamp):
        sub_parser.add_argument("--json", action="store_true", default=None, dest="json",
                                help="вывод в JSON")

    args = parser.parse_args(argv)
    # --json можно дать до или после команды; приоритет у общего флага
    args.json = bool(getattr(args, "json", False)) or bool(getattr(args, "json_global", False))
    try:
        return args.func(args)
    except MemoryError_ as exc:
        print(f"ОШИБКА памяти: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())