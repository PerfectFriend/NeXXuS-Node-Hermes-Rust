"""CLI слоя памяти и графа Project2.

    python3 -m p2_graph report   [--json] [--memory-dir DIR]
    python3 -m p2_graph validate [--json]
    python3 -m p2_graph dedupe   [--json] [--fix]
    python3 -m p2_graph graph    [--json] [--top N] [--types a,b]
    python3 -m p2_graph query WORD [--json] [--limit N]

Exit-коды: 0 — успех, 1 — ошибка данных (есть проблемы), 2 — ошибка ввода/файла.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from . import EDGE_TYPES, __version__
from .graph import build_graph, centrality, edge_type_counts, metrics, query as graph_query
from .loader import DEFAULT_DIR, MemoryError_, atomic_write, iter_insights, load_all
from .validate import clean_insights, validate_file

EXIT_OK = 0
EXIT_DATA = 1
EXIT_USAGE = 2


def _collect(args) -> Dict[str, Any]:
    files = load_all(args.memory_dir)
    insights = list(iter_insights(files))
    return {"files": files, "insights": insights}


def cmd_report(args) -> int:
    data = _collect(args)
    insights = data["insights"]
    kept, stats = clean_insights(insights)
    graph = build_graph(kept)
    m = metrics(graph)
    report = {
        "project": 2,
        "version": __version__,
        "files": len(data["files"]),
        "insights_total": len(insights),
        "insights_clean": len(kept),
        "junk": stats["junk"],
        "junk_reasons": stats["junk_reasons"],
        "duplicates": stats["duplicates"],
        "categories": _counter(i.get("category") for i in kept),
        "graph": {
            "nodes": m["nodes"],
            "edges": m["edges"],
            "density": m["density"],
            "components": m["components"],
            "largest_component": m["largest_component"],
            "isolated": m["isolated"],
            "avg_degree": m["avg_degree"],
            "edge_types": edge_type_counts(graph),
            "suppressed_keys": graph["suppressed"],
        },
        "top_central": centrality(graph, top=args.top),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return EXIT_OK


def _counter(values) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for v in values:
        key = str(v)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _print_report(r: Dict[str, Any]) -> None:
    g = r["graph"]
    print(f"Project2 — отчёт памяти и графа (p2_graph {r['version']})")
    print(f"  файлов:            {r['files']}")
    print(f"  инсайтов всего:    {r['insights_total']}")
    print(f"  после очистки:     {r['insights_clean']}")
    print(f"  мусор:             {r['junk']} {r['junk_reasons'] or ''}")
    print(f"  дубликатов:        {r['duplicates']}")
    print(f"  категории:         {r['categories']}")
    print("  --- граф ---")
    print(f"  узлов/рёбер:       {g['nodes']} / {g['edges']}")
    print(f"  типы рёбер:        {g['edge_types']}")
    print(f"  плотность:         {g['density']}")
    print(f"  компонент:         {g['components']} (крупнейшая {g['largest_component']})")
    print(f"  изолированных:     {g['isolated']}")
    print(f"  средняя степень:   {g['avg_degree']}")
    if g["suppressed_keys"]:
        print("  подавленные неразличающие ключи (не дают рёбер):")
        for s in g["suppressed_keys"]:
            print(f"    - {s['kind']} key={s['key']!r} покрывает {s['members']} узлов ({s['share']})")
    print("  --- топ по центральности ---")
    for i, row in enumerate(r["top_central"], 1):
        print(f"  {i:2}. d={row['degree']:<3} s={row['score']:<7} {row['topic']}")


def cmd_validate(args) -> int:
    data = _collect(args)
    problems: List[str] = []
    for f in data["files"]:
        problems.extend(validate_file(f))
    payload = {"problems": problems, "count": len(problems)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif problems:
        print(f"Проблем: {len(problems)}")
        for p in problems:
            print(f"  - {p}")
    else:
        print("Проблем схемы не найдено.")
    return EXIT_DATA if problems else EXIT_OK


def cmd_dedupe(args) -> int:
    data = _collect(args)
    total_junk = total_dups = 0
    written: List[str] = []
    for f in data["files"]:
        kept, stats = clean_insights(f["insights"])
        total_junk += stats["junk"]
        total_dups += stats["duplicates"]
        if args.fix and len(kept) != len(f["insights"]):
            new = {k: v for k, v in f.items() if not k.startswith("_")}
            new["insights"] = kept
            new["total_insights"] = len(kept)
            atomic_write(f["_path"], new)
            written.append(f["_path"])
    payload = {"junk": total_junk, "duplicates": total_dups, "fixed": written}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "ИСПРАВЛЕНО" if args.fix else "dry-run (без --fix ничего не записано)"
        print(f"мусор: {total_junk}, дубликатов: {total_dups} — {mode}")
        for p in written:
            print(f"  записан: {p}")
    return EXIT_OK


def cmd_graph(args) -> int:
    data = _collect(args)
    kept, _stats = clean_insights(data["insights"])
    types = [t.strip() for t in args.types.split(",")] if args.types else list(EDGE_TYPES)
    unknown = [t for t in types if t not in EDGE_TYPES]
    if unknown:
        print(f"Неизвестные типы рёбер: {unknown}; допустимы {list(EDGE_TYPES)}", file=sys.stderr)
        return EXIT_USAGE
    graph = build_graph(kept, edge_types=types, min_shared=args.min_shared)
    m = metrics(graph)
    payload = {
        "nodes": m["nodes"],
        "edges": m["edges"],
        "edge_types": edge_type_counts(graph),
        "density": m["density"],
        "components": m["components"],
        "largest_component": m["largest_component"],
        "isolated": graph["isolated"],
        "avg_degree": m["avg_degree"],
        "min_shared": args.min_shared,
        "suppressed_keys": graph["suppressed"],
        "top_central": centrality(graph, top=args.top),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"узлов: {payload['nodes']}, рёбер: {payload['edges']}")
        print(f"типы рёбер: {payload['edge_types']}")
        print(f"плотность: {payload['density']}, компонент: {payload['components']}, "
              f"изолированных: {payload['isolated']}")
        for i, row in enumerate(payload["top_central"], 1):
            print(f"  {i:2}. d={row['degree']:<3} {row['topic']}")
    return EXIT_OK


def cmd_query(args) -> int:
    data = _collect(args)
    kept, _stats = clean_insights(data["insights"])
    graph = build_graph(kept)
    hits = graph_query(graph, args.word, limit=args.limit)
    if args.json:
        print(json.dumps({"word": args.word, "hits": hits}, ensure_ascii=False, indent=2))
    elif not hits:
        print(f"По запросу {args.word!r} ничего не найдено.")
    else:
        print(f"Запрос {args.word!r}: найдено {len(hits)}")
        for i, h in enumerate(hits, 1):
            print(f"  {i:2}. s={h['score']:<7} {h['topic']}  [{h['category']}]")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="p2_graph", description="Память и граф знаний Project2")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--memory-dir", default=str(DEFAULT_DIR), help="каталог memory-файлов")
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("report", help="сводка памяти и графа")
    r.add_argument("--json", action="store_true")
    r.add_argument("--top", type=int, default=10)
    r.set_defaults(func=cmd_report)

    v = sub.add_parser("validate", help="проверка схемы инсайтов")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_validate)

    d = sub.add_parser("dedupe", help="мусор и дубли (по умолчанию dry-run)")
    d.add_argument("--json", action="store_true")
    d.add_argument("--fix", action="store_true", help="записать очищенное")
    d.set_defaults(func=cmd_dedupe)

    g = sub.add_parser("graph", help="метрики графа и центральность")
    g.add_argument("--json", action="store_true")
    g.add_argument("--top", type=int, default=10)
    g.add_argument("--types", default="", help="типы рёбер через запятую")
    g.add_argument("--min-shared", type=int, default=2,
                   dest="min_shared",
                   help="минимум общих значимых слов для ребра token_overlap")
    g.set_defaults(func=cmd_graph)

    q = sub.add_parser("query", help="поиск по корпусу")
    q.add_argument("word")
    q.add_argument("--json", action="store_true")
    q.add_argument("--limit", type=int, default=10)
    q.set_defaults(func=cmd_query)
    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.func(args)
    except MemoryError_ as exc:
        print(f"ОШИБКА памяти: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
