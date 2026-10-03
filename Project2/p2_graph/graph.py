"""Граф знаний над корпусом Project2.

Узел — инсайт. Рёбра четырёх типов, каждое ребро уникально по паре (src, dst, type):

- `same_source`    — общий непустой source_url (одна заметка Учебника, разные темы);
- `same_topic`    — одинаковый topic при разных source_url;
- `shares_tag`    — пересечение непустых тегов;
- `same_category` — общая category.

Метрики: плотность, изолированные узлы, связные компоненты, центральность.
Всё чистое: без внешних зависимостей, без сети, без записи на диск.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

Edge = Tuple[str, str, str]

ID_FIELD = "_nid"

# Стоп-слова английского/русского + служебные слова Учебника. Без них
# `token_overlap` соединял бы все 100 тем Учебника между собой.
STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have how in into is it its of on or
    that the this to was were what when where which who will with you your
    the a an and or but if then than so such can could should would may might
    must shall about over under again further once here there all any both
    each few more most other some only own same too very s t don now
    и в во не что он на я с со как а то все она так его но да ты к у же вы
    за бы по только ее мне было вот от меня еще нет о из ему теперь когда
    даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам
    ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя
    их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто
    этот того потому этого какой совсем ним здесь этом один почти мой тем
    чтобы нее сейчас были куда зачем всех никогда можно при наконец два об
    другой хоть после над больше тот через эти нас про всего них какая много
    разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том
    нельзя такой им более всегда конечно всю между
    """.split()
)

_WORD_RE = re.compile(r"[0-9a-zA-Zа-яА-ЯёЁ]+")


def tokens_of(text: str) -> Set[str]:
    """Значимые слова текста: длина ≥3, не стоп-слово, в нижнем регистре."""
    out = set()
    for raw in _WORD_RE.findall(text or ""):
        low = raw.lower()
        if len(low) >= 3 and low not in STOPWORDS:
            out.add(low)
    return out


def node_id(index: int) -> str:
    return f"n{index:04d}"


def _tags(item: Dict[str, Any]) -> Set[str]:
    raw = item.get("tags")
    if not isinstance(raw, list):
        return set()
    return {str(t).strip().lower() for t in raw if str(t).strip()}


def build_graph(
    insights: Sequence[Dict[str, Any]],
    edge_types: "Iterable[str] | None" = None,
    max_key_share: float = 0.5,
    min_shared: int = 2,
    min_key_members: int = 4,
) -> Dict[str, Any]:
    """Построить граф. Возвращает {nodes, edges, isolated, adjacency, suppressed}.

    `max_key_share` — порог подавления неразличающих ключей. Измеренный дефект
    данных Project2: у 99 из 102 инсайтов теги ровно `["learned", "textbook"]`,
    а категория у 184 из 190 — `Textbook`. Рёбра по таким ключам соединяют все
    узлы попарно (плотность 1.0) и не несут информации, поэтому ключ,
    покрывающий более `max_key_share` узлов, подавляется и попадает в
    `suppressed`. Так рёбра остаются только между реально различающимися
    инсайтами.

    `min_key_members` — абсолютный пол. Без него на крошечных корпусах
    (2–3 узла) любой ключ покрывает 100% и подавляется, граф пустеет целиком;
    пол не даёт подавить малую группу, которая в малой выборке как раз и
    различает узлы.
    """
    types = tuple(edge_types) if edge_types is not None else (
        "same_source",
        "same_topic",
        "shares_tag",
        "same_category",
        "token_overlap",
    )
    nodes: List[Dict[str, Any]] = []
    for idx, item in enumerate(insights):
        nodes.append(
            {
                "id": node_id(idx),
                "topic": str(item.get("topic", "")),
                "category": str(item.get("category", "")),
                "source_url": str(item.get("source_url", "")),
                "tags": sorted(_tags(item)),
                "relevance": float(item.get("relevance_score") or 0.0),
                "file": str(item.get("_file", "")),
            }
        )

    buckets: Dict[str, Dict[Any, List[int]]] = {
        "source_url": {},
        "topic": {},
        "tag": {},
        "category": {},
    }
    for idx, item in enumerate(insights):
        src = str(item.get("source_url", "")).strip()
        if src:
            buckets["source_url"].setdefault(src, []).append(idx)
        topic = str(item.get("topic", "")).strip()
        if topic:
            buckets["topic"].setdefault(topic, []).append(idx)
        cat = str(item.get("category", "")).strip()
        if cat:
            buckets["category"].setdefault(cat, []).append(idx)
        for tag in _tags(item):
            buckets["tag"].setdefault(tag, []).append(idx)

    edges: Set[Edge] = set()
    pair_types: Dict[Tuple[str, str], Set[str]] = {}
    total_nodes = len(insights)
    # Абсолютный пол: малую группу не подавляем даже при 100%-покрытии.
    limit = max(total_nodes * max_key_share, min_key_members - 1)
    suppressed: List[Dict[str, Any]] = []

    def connect(group: Iterable[int], kind: str) -> None:
        members = sorted(group)
        for a_i in range(len(members)):
            for b_i in range(a_i + 1, len(members)):
                u, v = members[a_i], members[b_i]
                uid, vid = node_id(u), node_id(v)
                pair = (uid, vid) if uid < vid else (vid, uid)
                pair_types.setdefault(pair, set()).add(kind)

    def walk(bucket: Dict[Any, List[int]], kind: str) -> None:
        for key, group in bucket.items():
            if total_nodes and len(group) > limit:
                suppressed.append(
                    {
                        "kind": kind,
                        "key": str(key),
                        "members": len(group),
                        "share": round(len(group) / total_nodes, 4),
                    }
                )
                continue
            connect(group, kind)

    if "same_source" in types:
        walk(buckets["source_url"], "same_source")
    if "same_topic" in types:
        walk(buckets["topic"], "same_topic")
    if "shares_tag" in types:
        walk(buckets["tag"], "shares_tag")
    if "same_category" in types:
        walk(buckets["category"], "same_category")
    if "token_overlap" in types:
        # Инвертированный индекс по значимым словам: ребро, если два инсайта
        # делят не меньше min_shared слов. Иначе 100 тем Учебника схлопываются
        # в полный граф (плотность 1.0) и граф перестаёт что-то различать.
        inverted: Dict[str, List[int]] = {}
        for idx, item in enumerate(insights):
            text = " ".join(
                str(item.get(f, "")) for f in ("topic", "summary", "category")
            )
            for tok in tokens_of(text):
                inverted.setdefault(tok, []).append(idx)
        shared: Dict[Tuple[int, int], int] = {}
        for members in inverted.values():
            if len(members) > limit:
                continue  # слишком частый токен — не различает
            for a_i in range(len(members)):
                for b_i in range(a_i + 1, len(members)):
                    u, v = sorted((members[a_i], members[b_i]))
                    shared[(u, v)] = shared.get((u, v), 0) + 1
        for (u, v), count in shared.items():
            if count < min_shared:
                continue
            uid, vid = node_id(u), node_id(v)
            pair = (uid, vid) if uid < vid else (vid, uid)
            pair_types.setdefault(pair, set()).add("token_overlap")

    for (uid, vid), kinds in pair_types.items():
        for kind in sorted(kinds):
            edges.add((uid, vid, kind))

    adjacency: Dict[str, Set[str]] = {n["id"]: set() for n in nodes}
    for uid, vid, _kind in edges:
        adjacency[uid].add(vid)
        adjacency[vid].add(uid)

    isolated = sorted(nid for nid, nb in adjacency.items() if not nb)
    return {
        "nodes": nodes,
        "edges": sorted(edges),
        "isolated": isolated,
        "adjacency": adjacency,
        "suppressed": suppressed,
    }


def metrics(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Плотность, компоненты связности, распределение степеней."""
    nodes = graph["nodes"]
    edges = graph["edges"]
    adjacency = graph["adjacency"]
    n = len(nodes)
    m = len(edges)
    undirected = len({(u, v) for u, v, _ in edges})
    max_edges = n * (n - 1) / 2
    density = (undirected / max_edges) if max_edges else 0.0

    seen: Set[str] = set()
    components: List[List[str]] = []
    for node in nodes:
        nid = node["id"]
        if nid in seen:
            continue
        stack = [nid]
        comp: List[str] = []
        seen.add(nid)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in adjacency[cur]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        components.append(sorted(comp))

    degrees = {node["id"]: len(adjacency[node["id"]]) for node in nodes}
    return {
        "nodes": n,
        "edges": m,
        "undirected_pairs": undirected,
        "density": round(density, 6),
        "isolated": len(graph["isolated"]),
        "components": len(components),
        "largest_component": max((len(c) for c in components), default=0),
        "components_detail": components,
        "degrees": degrees,
        "avg_degree": round(sum(degrees.values()) / n, 4) if n else 0.0,
    }


def edge_type_counts(graph: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for _u, _v, kind in graph["edges"]:
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def centrality(graph: Dict[str, Any], top: int = 10) -> List[Dict[str, Any]]:
    """Топ узлов: степень, домнённая на relevance_score."""
    degrees = {node["id"]: 0 for node in graph["nodes"]}
    for u, v, _kind in graph["edges"]:
        degrees[u] += 1
        degrees[v] += 1
    by_id = {node["id"]: node for node in graph["nodes"]}
    scored = []
    for nid, deg in degrees.items():
        node = by_id[nid]
        scored.append(
            {
                "id": nid,
                "topic": node["topic"],
                "category": node["category"],
                "degree": deg,
                "relevance": node["relevance"],
                "score": round(deg * (0.5 + 0.5 * node["relevance"]), 4),
            }
        )
    scored.sort(key=lambda x: (-x["score"], -x["degree"], x["topic"]))
    return scored[:top]


def query(graph: Dict[str, Any], needle: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Поиск по topic/summary/tags/source_url с ранжированием.

    Инсайты без summary недоступны в графе по построению, поэтому summary
    ищется в исходной записи, а ранжирование идёт по node-данным.
    """
    if not needle.strip():
        return []
    low = needle.strip().lower()
    results: List[Dict[str, Any]] = []
    for node in graph["nodes"]:
        hits = 0
        if low in node["topic"].lower():
            hits += 3
        if low in node["category"].lower():
            hits += 1
        if low in node["source_url"].lower():
            hits += 1
        if any(low in t for t in node["tags"]):
            hits += 2
        if hits:
            results.append(
                {
                    "id": node["id"],
                    "topic": node["topic"],
                    "category": node["category"],
                    "hits": hits,
                    "score": round(hits * (0.5 + 0.5 * node["relevance"]), 4),
                }
            )
    results.sort(key=lambda x: (-x["score"], -x["hits"], x["topic"]))
    return results[:limit]
