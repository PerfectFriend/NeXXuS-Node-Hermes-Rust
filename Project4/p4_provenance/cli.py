#!/usr/bin/env python3
"""CLI форензики памяти Project4.

    python -m p4_provenance <команда> [аргументы]

Команды: validate, load, fingerprint, repro, identity, audit, metrics, search,
canon, canary, report.

Код возврата 0 — успех (в том числе DRIFT у canary: это подтверждение, что дефект
жив, а не сбой инструмента). Код 1 — ошибка данных или неожиданный статус.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import SIBLING_PROJECTS
from . import attribution, canon, canary, fingerprint, loader, metrics, repro

REPO = Path(__file__).resolve().parent.parent.parent


def _out(data: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        print(data)


def _records(args: argparse.Namespace) -> List[Dict[str, Any]]:
    return loader.iter_records(args.memory or loader.DEFAULT_DIR)


# --------------------------------------------------------------------------
# команды
# --------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    report = loader.validate_corpus(args.memory or loader.DEFAULT_DIR)
    _out(report)
    return 0 if report["valid"] else 1


def cmd_load(args: argparse.Namespace) -> int:
    data = loader.load(args.file)
    _out(
        {
            "file": data.get("_source_file"),
            "cycle": data.get("cycle"),
            "project": data.get("project"),
            "records": len(data["insights"]),
            "markers_removed": data.get("_markers_removed", []),
        }
    )
    return 0


def cmd_fingerprint(args: argparse.Namespace) -> int:
    _out(fingerprint.corpus_fingerprints(args.memory or loader.DEFAULT_DIR))
    return 0


def cmd_repro(args: argparse.Namespace) -> int:
    report = repro.repro_report(args.repo or REPO)
    _out(report)
    return 0 if report["defect_confirmed"] else 1


def cmd_identity(args: argparse.Namespace) -> int:
    report = fingerprint.identity_report(
        args.memory or loader.DEFAULT_DIR, args.repo or REPO, args.neighbours
    )
    report.pop("own_fingerprints", None)
    _out(report)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    records = _records(args)
    _out(
        {
            "addressing": attribution.default_addressing_audit(records),
            "ownership": attribution.attribute_corpus(records),
            "repetition": attribution.repetition_report(records),
        }
    )
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    _out(metrics.metrics(_records(args)))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    records = _records(args)
    tags = args.tag or None
    _out(
        metrics.search_summary(
            records,
            args.query,
            topic=args.topic,
            category=args.category,
            source_type=args.source_type,
            cycle=args.cycle,
            tags=tags,
            min_score=args.min_score,
            max_score=args.max_score,
        )
    )
    return 0


def cmd_fields(args: argparse.Namespace) -> int:
    _out(metrics.unique_filter_values(_records(args)))
    return 0


def cmd_canon(args: argparse.Namespace) -> int:
    records = _records(args)
    canonical = canon.canonicalise(records)
    result = {k: v for k, v in canonical.items() if k != "records"}
    result["top"] = [
        {"topic": r.get("topic"), "occurrences": r["_occurrences"], "sources": r["_sources"]}
        for r in canonical["records"][:10]
    ]
    if args.neighbour:
        from .paths import sibling_memory_dir

        other_dir = sibling_memory_dir(args.neighbour, args.repo or REPO)
        if other_dir.exists():
            result["own_vs_neighbour"] = canon.only_mine(
                canonical, loader.iter_records(other_dir)
            )
        else:
            result["own_vs_neighbour"] = {"error": f"нет каталога памяти у {args.neighbour}"}
    _out(result)
    return 0


def cmd_canary(args: argparse.Namespace) -> int:
    report = canary.canary(args.memory or loader.DEFAULT_DIR, args.repo or REPO, args.neighbours)
    print(canary.line(report))
    if args.json:
        _out(report)
    return canary.exit_code(report)


def cmd_report(args: argparse.Namespace) -> int:
    from .report import render_report

    text = render_report(
        args.memory or loader.DEFAULT_DIR, args.repo or REPO, args.neighbours
    )
    if args.out:
        target = Path(args.out)
        if not target.is_absolute():
            target = Path(args.out)
        target.write_text(text, encoding="utf-8")
        print(f"отчёт записан: {target}")
    else:
        print(text)
    return 0


COMMANDS = {
    "validate": cmd_validate,
    "load": cmd_load,
    "fingerprint": cmd_fingerprint,
    "repro": cmd_repro,
    "identity": cmd_identity,
    "audit": cmd_audit,
    "metrics": cmd_metrics,
    "search": cmd_search,
    "fields": cmd_fields,
    "canon": cmd_canon,
    "canary": cmd_canary,
    "report": cmd_report,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="p4_provenance",
        description="Форензика памяти Project4: происхождение и вина данных.",
    )
    parser.add_argument(
        "-m", "--memory", help="каталог memory (по умолчанию memory/ внутри Project4)"
    )
    parser.add_argument("-r", "--repo", help="корень LivingCode (для соседей и горячего кода)")
    parser.add_argument(
        "-n", "--neighbours", nargs="*", default=list(SIBLING_PROJECTS),
        help="соседние проекты для сверки (по умолчанию Project1..3)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="проверить корпус")
    load_parser = sub.add_parser("load", help="прочитать один файл памяти")
    load_parser.add_argument("file")
    sub.add_parser("fingerprint", help="отпечатки циклов")
    sub.add_parser("repro", help="живое воспроизведение дефекта адресации")
    sub.add_parser("identity", help="сверка с соседними проектами")
    sub.add_parser("audit", help="адресация, происхождение, повторы")
    sub.add_parser("metrics", help="метрики корпуса")
    fields_parser = sub.add_parser("fields", help="доступные значения фильтров")
    fields_parser.set_defaults(func=cmd_fields)

    search_parser = sub.add_parser("search", help="поиск по корпусу")
    search_parser.add_argument("query")
    search_parser.add_argument("--topic")
    search_parser.add_argument("--category")
    search_parser.add_argument("--source-type")
    search_parser.add_argument("--cycle", type=int)
    search_parser.add_argument("--tag", action="append")
    search_parser.add_argument("--min-score", type=float)
    search_parser.add_argument("--max-score", type=float)

    canon_parser = sub.add_parser("canon", help="канонизация корпуса")
    canon_parser.add_argument("--neighbour", help="сравнить с проектом-соседом по имени")

    canary_parser = sub.add_parser("canary", help="канарейка регрессии")
    canary_parser.add_argument("--json", action="store_true")

    report_parser = sub.add_parser("report", help="сгенерировать PROVENANCE_REPORT.md")
    report_parser.add_argument("--out", help="файл отчёта")

    for name, func in COMMANDS.items():
        sub.choices[name].set_defaults(func=func)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    try:
        return func(args)
    except (loader.MemoryInvalid, repro.HotModuleMissing) as exc:
        print(f"ошибка данных: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())