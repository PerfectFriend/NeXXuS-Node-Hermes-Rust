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
from .loader import MemoryError_, iter_memory_files, load, save_atomic
from .validate import clean_insights, summarize, validate_document

DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def collect(root: Path):
    files = iter_memory_files(root)
    return files, [load(f) for f in files]


def cmd_report(args) -> int:
    files, docs = collect(args.root)
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
    changes = []
    for path, doc in zip(files, docs):
        kept, stats = clean_insights(doc["insights"])
        if stats["kept"] == stats["input"]:
            continue
        changes.append((path, doc, kept, stats))
        marker = "FIX" if args.fix else "dry-run"
        print(f"[{marker}] {path.name}: {stats['input']} → {stats['kept']} "
              f"(мусор {stats['junk']}, дубли {stats['duplicates']})")

    if not changes:
        print("Чистить нечего: все файлы уже чистые.")
        return 0
    if not args.fix:
        print(f"Итого к очистке файлов: {len(changes)} (запусти с --fix)")
        return 0

    for path, doc, kept, stats in changes:
        payload = dict(doc)
        payload["insights"] = kept
        payload["total_insights"] = len(kept)
        save_atomic(path, payload, backup=True)
        print(f"  записано: {path.name} ({stats['kept']} записей), бэкап {path.name}.bak")
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
    p_report.set_defaults(func=cmd_report)
    p_validate = sub.add_parser("validate", help="проверка схемы")
    p_validate.set_defaults(func=cmd_validate)
    p_dedupe = sub.add_parser("dedupe", help="дедупликация и фильтрация мусора")
    p_dedupe.add_argument("--fix", action="store_true", help="записать изменения (по умолчанию dry-run)")
    p_dedupe.set_defaults(func=cmd_dedupe)

    p_chron = sub.add_parser("chronicle", help="дописать запись в журнал проекта")
    p_chron.add_argument("--title", required=True, help="заголовок записи (и защита от повтора)")
    p_chron.add_argument("--body", default="", help="текст записи")
    p_chron.add_argument("--file", default=CHRONICLE_NAME, help="имя файла журнала")
    p_chron.add_argument("--stamp", default="", help="метка времени (для тестов/кронов)")
    p_chron.add_argument("--stats", action="store_true", help="дописать сводку качества памяти")
    p_chron.set_defaults(func=cmd_chronicle)

    # --json разрешён и до, и после имени команды
    for sub_parser in (p_report, p_validate, p_dedupe, p_chron):
        sub_parser.add_argument("--json", action="store_true", default=None, dest="json",
                                help="вывод в JSON")

    args = parser.parse_args(argv)
    # --json можно дать до или после команды; приоритет у общего флага
    args.json = bool(args.json) or bool(getattr(args, "json_global", False))
    try:
        return args.func(args)
    except MemoryError_ as exc:
        print(f"ОШИБКА памяти: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())