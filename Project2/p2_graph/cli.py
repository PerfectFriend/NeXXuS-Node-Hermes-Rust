"""CLI слоя памяти и графа Project2.

    python3 -m p2_graph report   [--json] [--memory-dir DIR]
    python3 -m p2_graph validate [--json]
    python3 -m p2_graph dedupe   [--json] [--fix]
    python3 -m p2_graph graph    [--json] [--top N] [--types a,b]
    python3 -m p2_graph query WORD [--json] [--limit N]
    python3 -m p2_graph freshness [--json]

Exit-коды: 0 — успех, 1 — ошибка данных (есть проблемы), 2 — ошибка ввода/файла.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
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
        "isolated_count": m["isolated"],
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
              f"изолированных: {payload['isolated_count']}")
        for i, row in enumerate(payload["top_central"], 1):
            print(f"  {i:2}. d={row['degree']:<3} {row['topic']}")
    return EXIT_OK


def _conclusions(graph, m, kept, stats) -> List[str]:
    """Выводы, выведенные из данных, а не расписанные заранее.

    Раньше этот раздел содержал конкретные числа и названия тем, написанные
    руками; на другом корпусе они становились ложью. Теперь каждая фраза
    опирается на посчитанную величину.
    """
    out: List[str] = []

    by_id = {n["id"]: n for n in graph["nodes"]}
    comps = m["components_detail"]
    biggest = max(comps, key=len) if comps else []
    if len(biggest) > 1:
        topics = [by_id[nid]["topic"] for nid in biggest if nid in by_id]
        shown = ", ".join(f"«{t}»" for t in topics[:3])
        more = f" и ещё {len(topics) - 3}" if len(topics) > 3 else ""
        out.append(
            f"Крупнейшая компонента ({len(biggest)} узла): {shown}{more}. "
            "Эти темы связаны общими значимыми словами — настоящая связь, а не метаданные."
        )
    else:
        out.append("Крупнейшая компонента состоит из одного узла: связей нет вовсе.")

    total = len(kept)
    if total:
        iso_share = m["isolated"] / total
        out.append(
            f"Изолированных узлов {m['isolated']} из {total} ({iso_share:.0%}). "
            "Остальное держится на перечисленных компонентах."
        )

    kinds = edge_type_counts(graph)
    if graph["suppressed"]:
        kinds_txt = ", ".join(f"`{s['kind']}`" for s in graph["suppressed"])
        out.append(
            f"Подавлено неразличающих ключей: {len(graph['suppressed'])} ({kinds_txt}). "
            "Ключ, покрывающий больше половины узлов, — константа, а не структура: "
            "он соединил бы все узлы попарно."
        )
    if kinds:
        out.append(
            f"Держат структуру: {kinds}. Если в будущем `professor_sync.py` начнёт "
            "различать теги и категории по темам, добавятся и остальные типы рёбер."
        )
    else:
        out.append("Ни один тип рёбер не дал связей: корпус не несёт структуры.")

    if stats["junk"]:
        share = stats["junk"] / max(len(graph["nodes"]) + stats["junk"], 1)
        out.append(
            f"Мусор — {stats['junk']} записей ({share:.0%} корпуса), причина: "
            f"{stats['junk_reasons']}. Это меньше, чем вырожденность метаданных."
        )
    out.append(
        "Данные не изменялись: отчёт только читает. Правка памяти — отдельная "
        "команда `dedupe --fix`, и только по явному решению."
    )
    return out


def cmd_report_file(args) -> int:
    """Сгенерировать GRAPH_REPORT.md из живых данных.

    Числа в файле берутся из тех же функций, что и CLI, поэтому отчёт не может
    разойтись с кодом: файл либо перезаписан, либо не создан вовсе.
    """
    data = _collect(args)
    kept, stats = clean_insights(data["insights"])
    graph = build_graph(kept, min_shared=args.min_shared)
    m = metrics(graph)

    # Чувствительность к порогу: показывает, что min_shared — решение, а не магия.
    sweep = []
    for threshold in (1, 2, 3, 4, 5):
        sm = metrics(build_graph(kept, min_shared=threshold))
        sweep.append((threshold, sm))

    lines: List[str] = []
    lines.append("# Граф знаний Project2 — отчёт")
    lines.append("")
    lines.append("Сгенерировано кодом: `python3 -m p2_graph graph-report`.")
    lines.append("Не редактировать руками — файл перезаписывается целиком.")
    lines.append("")
    lines.append(f"Порог `min_shared = {args.min_shared}` (минимум общих значимых слов для ребра).")
    lines.append("")
    lines.append("## Корпус")
    lines.append("")
    lines.append(f"- файлов памяти: {len(data['files'])}")
    lines.append(f"- записей всего: {len(data['insights'])}")
    lines.append(f"- мусорных (topic=Unknown/пустое): {stats['junk']} {stats['junk_reasons'] or ''}")
    lines.append(f"- дубликатов на объединённом корпусе: {stats['duplicates']}")
    lines.append(f"- записей после очистки: {len(kept)}")
    lines.append("")
    lines.append("## Граф")
    lines.append("")
    lines.append(f"- узлов: {m['nodes']}")
    lines.append(f"- рёбер: {m['edges']}")
    lines.append(f"- типы рёбер: {edge_type_counts(graph)}")
    lines.append(f"- плотность: {m['density']}")
    lines.append(f"- компонент связности: {m['components']}, крупнейшая {m['largest_component']}")
    lines.append(f"- изолированных узлов: {m['isolated']}")
    lines.append(f"- средняя степень: {m['avg_degree']}")
    lines.append("")
    lines.append("## Подавленные неразличающие ключи")
    lines.append("")
    lines.append("Ключ, покрывающий больше половины узлов, структуры не даёт и подавляется.")
    lines.append("")
    lines.append("| тип | ключ | узлов | доля |")
    lines.append("| --- | --- | --- | --- |")
    for s in graph["suppressed"]:
        lines.append(f"| {s['kind']} | `{s['key']}` | {s['members']} | {s['share']} |")
    lines.append("")
    lines.append("## Чувствительность к порогу")
    lines.append("")
    lines.append("| min_shared | рёбер | плотность | компонент | крупнейшая | изолированных |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for threshold, sm in sweep:
        lines.append(
            f"| {threshold} | {sm['edges']} | {sm['density']} | {sm['components']} "
            f"| {sm['largest_component']} | {sm['isolated']} |"
        )
    lines.append("")
    if sweep:
        loose_t, loose = sweep[0]
        chosen_t, chosen = next(((t, s) for t, s in sweep if t == args.min_shared),
                                (args.min_shared, m))
        if loose_t != chosen_t:
            out = (
                f"Порог {loose_t} даёт {loose['edges']} рёбер и {loose['components']} "
                f"компонент, но это шум: одно общее слово склеивает несвязанные темы. "
                f"Порог {chosen_t} — рабочий компромисс ({chosen['edges']} рёбер, "
                f"{chosen['components']} компонент)."
            )
        else:
            out = f"Порог {chosen_t} выбран и даёт {chosen['edges']} рёбер."
        lines.append(out)
    lines.append("")
    lines.append("## Топ по центральности")
    lines.append("")
    lines.append("| # | узел | тема | степень | relevance | score |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for i, row in enumerate(centrality(graph, top=args.top), 1):
        lines.append(
            f"| {i} | {row['id']} | {row['topic']} | {row['degree']} "
            f"| {row['relevance']} | {row['score']} |"
        )
    lines.append("")
    lines.append("## Что из этого следует")
    lines.append("")
    lines.extend(_conclusions(graph, m, kept, stats))
    lines.append("")

    text = "\n".join(lines)
    if args.out:
        out = Path(args.out)
    else:
        out = Path(__file__).resolve().parent.parent / "GRAPH_REPORT.md"
    out.write_text(text, encoding="utf-8")
    print(f"Записан {out} ({len(kept)} записей, {m['edges']} рёбер)")
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


def cmd_freshness(args) -> int:
    """Свежесть корпуса: инверсии порядка имён, потери, подменённое происхождение."""
    from .provenance import freshness_report, origin_findings

    data = _collect(args)
    files = data.get("files") or []
    if not files:
        print("Нет файлов памяти для анализа.")
        return EXIT_DATA
    rep = freshness_report(files)
    kept, _stats = clean_insights(data["insights"])
    findings = origin_findings(kept)

    if args.json:
        print(json.dumps(
            {
                "order_is_chronological": rep["order_is_chronological"],
                "inverted_count": rep["inverted_count"],
                "inverted_files": rep["inverted_files"],
                "lost": rep["lost"],
                "lost_detail": rep["lost_detail"],
                "origin_findings": findings,
                "origin_count": len(findings),
            },
            ensure_ascii=False, indent=2,
        ))
        # Инверсия без потерь — это сведения, не дефект: дедуп по свежести
        # (пункт 13) уже выбирает победителя верно. Exit-код сигналит
        # именно о потерянных записях, как и обещает пункт 18 плана.
        return EXIT_DATA if rep["lost"] else EXIT_OK

    print(f"Файлов памяти: {len(rep['files'])}")
    if rep["order_is_chronological"]:
        print("Порядок чтения совпадает с хронологией: да")
    else:
        инв = rep.get("inverted_count", 0)
        print(
            "Порядок чтения НЕ совпадает с хронологией: "
            f"инверсий {инв}, потеряно свежих записей {rep.get('lost', 0)}"
        )
        for det in rep["lost_detail"]:
            print(f"  {det['file']}  synced_at={det['synced_at']}  "
                  f"вытеснено записей: {det['overwritten_by_fresher']}")
        print(f"Всего потеряно записей при дедупе по имени файла: {rep['lost']}")
    if findings:
        print(f"Подменённое происхождение: {len(findings)}")
        for f in findings[:20]:
            print(f"  [{f['index']}] {f['topic'][:70]} — {f['source_type']} {f['source_url'][:50]}")
            for reason in f["reasons"]:
                print(f"        · {reason}")
        if len(findings) > 20:
            print(f"  … ещё {len(findings) - 20}")
    return EXIT_DATA if rep["lost"] else EXIT_OK


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

    r = sub.add_parser("graph-report", help="сгенерировать GRAPH_REPORT.md")
    r.add_argument("--min-shared", type=int, default=2, dest="min_shared")
    r.add_argument("--top", type=int, default=12)
    r.add_argument("--out", default="", help="куда писать (по умолчанию GRAPH_REPORT.md рядом с пакетом)")
    r.set_defaults(func=cmd_report_file)

    q = sub.add_parser("query", help="поиск по корпусу")
    q.add_argument("word")
    q.add_argument("--json", action="store_true")
    q.add_argument("--limit", type=int, default=10)
    q.set_defaults(func=cmd_query)

    fz = sub.add_parser("freshness", help="свежесть корпуса и подменённое происхождение")
    fz.add_argument("--json", action="store_true")
    fz.set_defaults(func=cmd_freshness)
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
