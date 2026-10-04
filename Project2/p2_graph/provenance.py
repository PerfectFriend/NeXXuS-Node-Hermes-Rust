"""Свежесть, происхождение и константность полей корпуса Project2.

Три класса дефектов, измеренных на штатных данных 2026-10-03.

1. **Инверсия свежести.** Имя файла (`professor_insights_cycle_1351.json`)
   задаёт порядок чтения, но номер цикла не хронологичен: `cycle_1351`
   синхронизирован `2026-08-14`, а `cycle_001` — `2026-08-16`, то есть
   «старший по имени» файл на 2 дня свежее... нет, на 2 дня **старее**.
   При дедупе «первый побеждает» именно `cycle_001` выигрывает у 1351 только
   потому, что стоит в сортировке раньше, а не потому, что свежее. Правило
   выбора победителя должно опираться на `timestamp` записи, иначе однажды
   отредактированная запись молча откатится к старой копии.

2. **Подмена происхождения.** Запись с `source_type == "textbook"` и
   `source_url` на внешний домен (не vault, не `.md`) — это не учебник.
   Такой мусор идёт от сканера, тащившего навигацию сайта.

3. **Константные поля.** Поле, где у всех записей одно значение, ничего не
   различает. `applicable_projects == [1,2,3,4]` у всех 190 записей — значит
   оно не несёт информации, и любой фильтр по нему бесполезен.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "parse_ts",
    "insight_freshness",
    "file_freshness",
    "dedupe_by_freshness",
    "freshness_report",
    "origin_findings",
    "field_profile",
    "consolidate_insights",
    "stale_duplicates",
    "plan_freshness_fix",
    "apply_freshness_fix",
    "MARK_SUPERSEDED",
    "MARK_ORIGIN",
    "CONSTANT_SHARE",
]

# Пометки, которые `--fix` проставляет прямо в записи. Не служебные поля с
# подчёркиванием: они должны быть видны тому, кто читает файл глазами, —
# именно ради этого пункт 19 и формулировался как «разметить», а не «удалить».
MARK_SUPERSEDED = "superseded_by"
MARK_ORIGIN = "origin_issue"

# Порог «поле ничего не различает»: одно значение у этой доли записей.
CONSTANT_SHARE = 0.9


def parse_ts(value: Any) -> Optional[float]:
    """ISO-8601 → epoch-секунды. None, если значение не разбирается.

    Ответ наивный: корпус состоит из меток UTC с `+00:00`, поэтому смещение
    не меняет порядок. Для смешанных зон нужен нормализующий разбор — он
    не нужен здесь и не делается молча.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.timestamp()
    return dt.timestamp()


def insight_freshness(item: Dict[str, Any], fallback: Optional[float] = None) -> Optional[float]:
    """Свежесть одной записи: её `timestamp`, иначе `synced_at` файла."""
    got = parse_ts(item.get("timestamp"))
    if got is not None:
        return got
    return fallback


def file_freshness(data: Dict[str, Any]) -> Optional[float]:
    """Свежесть memory-файла по `synced_at`."""
    return parse_ts(data.get("synced_at"))


_CYCLE_IN_NAME = re.compile(r"cycle[_-]?(\d+)", re.IGNORECASE)


def _cycle_of(data: Dict[str, Any]) -> int:
    """Номер цикла файла: из метаданных, иначе из имени `..._cycle_012....`.

    Имя — единственный источник номера для файлов, пришедших без
    `_cycle`; без него порядок чтения вырождается в порядок выдачи
    каталога, а инверсию нечем объяснить.
    """
    raw = data.get("_cycle")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    match = _CYCLE_IN_NAME.search(str(data.get("_path", "")))
    return int(match.group(1)) if match else -1


def file_order_report(files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Расхождение между порядком чтения и тем, что файлы на самом деле.

    Файлы приходят **в порядке чтения** — `load_all()` отсортировал их
    по имени файла, а имя обычно несёт номер цикла. Пересортировывать
    их здесь нельзя: отчёт измеряет расхождение между порядком чтения
    и хронологией, а внутренняя сортировка уничтожила бы его ровно в
    том случае, когда оно есть.

    Файл помечается `inverted`, если читается позже, а при этом:

    * у него номер цикла МЕНЬШЕ, чем у уже прочитанного (порядок чтения
      не следует за номерами циклов — верный признак того, что сортировка
      по имени не отражает порядок появления, например из-за неравной
      ширины номера в именах `cycle_9` / `cycle_12`);
    * либо он СТАРШЕ уже прочитанного (файл со свежей синхронизацией
      прочитан раньше файла с более старой).

    Чего отчёт не делает: файлу без номера цикла и без `synced_at` ничего
    неизвестно, и флаг у него всегда False — лучше молчание, чем выдумка.

    Возвращает по файлу: позицию в порядке чтения, `synced_at`, номер
    цикла, флаг `inverted` и максимум свежести среди прочитанных ранее.
    """
    rows: List[Dict[str, Any]] = []
    for pos, data in enumerate(files):
        fresh = file_freshness(data)
        rows.append(
            {
                "position": pos,
                "file": data.get("_path", "?"),
                "cycle": _cycle_of(data),
                "synced_at": data.get("synced_at"),
                "freshness": fresh,
                "insights": len(data.get("insights") or []),
            }
        )
    best_before: Optional[float] = None
    max_cycle_before = -1
    for row in rows:
        fresh = row["freshness"]
        cycle = row["cycle"]
        known = cycle >= 0
        # Оси независимы: отсутствие номера цикла отменяет только проверку
        # порядка циклов, но не хронологию — по `synced_at` файл судим.
        inverted = (known and cycle < max_cycle_before) or (
            fresh is not None and best_before is not None and fresh < best_before
        )
        row["inverted"] = inverted
        row["newer_before"] = best_before
        if fresh is not None and (best_before is None or fresh > best_before):
            best_before = fresh
        if known and cycle > max_cycle_before:
            max_cycle_before = cycle
    return rows


def dedupe_by_freshness(
    items: Iterable[Any],
    fallback: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Дедуп по (topic, source_url), побеждает более свежая запись.

    Элемент потока — либо запись (dict), либо кортеж ``(запись, fallback)``:
    свежесть файла подставляется конкретной записи, а не всему вызову.
    Записи с неразбираемой свежестью считаются самыми старыми: без timestamp
    нельзя доказать, что запись новее, поэтому она уступает любой датированной.

    Возвращает (список, статистика). Статистика:
        - `replaced` — сколько записей вытеснено копией с большей свежестью;
        - `stale_wins` — сколько раз вытеснение произошло ЗА СЧЁТ подставленной
          свежести: победитель не имеет собственной даты (свежесть взята из
          файла) и при этом вытеснил запись, чья собственная дата разбиралась.
          Это самый подозрительный класс: файл с поздней mtime перебил
          датированную запись, и такой выбор нельзя принять на веру — смотреть
          глазами по `lost_detail` в `freshness_report`;
        - `undated_wins` — сколько записей без собственной даты выиграли
          дедуп (широкий счётчик, включает и предыдущий класс);
        - `unparsable` — записи без даты и без подставленной свежести,
          они всегда проигрывают и остаются самыми старыми.
    """
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []
    stats = {"replaced": 0, "stale_wins": 0, "unparsable": 0, "undated_wins": 0}

    for pos, entry in enumerate(items):
        per_item_fb: Optional[float] = None
        if isinstance(entry, tuple):
            item, per_item_fb = entry[0], entry[1]
        else:
            item = entry
        if not isinstance(item, dict):
            continue
        key = (str(item.get("topic", "")), str(item.get("source_url", "")))
        fb = per_item_fb if per_item_fb is not None else fallback
        fresh = insight_freshness(item, fallback=fb)
        if fresh is None:
            stats["unparsable"] += 1
            rank = float("-inf")
        else:
            rank = fresh
        cur = best.get(key)
        if cur is None:
            best[key] = {"item": item, "rank": rank, "fresh": fresh, "pos": pos}
            order.append(key)
            continue
        cur_rank = cur["rank"]
        # Ничья по свежести (обе копии без своей даты, свежесть подставлена
        # из одного файла) — выбор чисто позиционный: побеждает более поздняя,
        # потому что файл дописывали. Переигрывание при строго МЕНЬШЕЙ
        # свежести по-прежнему запрещено.
        tie = rank == cur_rank and rank != float("-inf")
        if rank > cur_rank or tie:
            # Счётчики «недоказанного» вытеснения смотрят на СОБСТВЕННУЮ дату
            # записи, а не на итоговую свежесть: подставленный из файла
            # fallback не должен делать подставную запись датированной.
            self_dated = parse_ts(item.get("timestamp")) is not None
            if not self_dated:
                stats["undated_wins"] += 1
                if parse_ts(cur["item"].get("timestamp")) is not None:
                    stats["stale_wins"] += 1
            stats["replaced"] += 1
            best[key] = {"item": item, "rank": rank, "fresh": fresh, "pos": pos}

    kept = [best[k]["item"] for k in order]
    stats["kept"] = len(kept)
    return kept, stats


def freshness_report(files: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Полный отчёт: порядок файлов, инверсии, потери свежести.

    `lost` — сколько записей в файлах, стоящих в порядке чтения позже более
    свежих, были бы вытеснены копией из более свежего файла. Это те записи,
    ради которых сортировка по имени файла опасна.
    """
    rows = file_order_report(files)
    inverted_files = [r for r in rows if r["inverted"]]

    # Потери: для каждого файла-инверсии считаем, сколько его записей
    # дублируют запись из БОЛЕЕ СВЕЖЕГО файла, стоящего раньше.
    #
    # Уже помеченные записи (`superseded_by`, пункт 19) из счёта исключены:
    # после `--fix` дефект считается закрытым, и повторный прогон обязан
    # дать 0 — иначе метка ничего не значит, а только прячет данные.
    lost = 0
    details: List[Dict[str, Any]] = []
    for row in rows:
        if not row["inverted"]:
            continue
        here = next(d for d in files if d.get("_path") == row["file"])
        here_fresh = row["freshness"]
        lost_keys = 0
        marked = 0
        for earlier in rows:
            if earlier["freshness"] is None or here_fresh is None:
                continue
            if earlier["freshness"] <= here_fresh:
                continue
            other = next(d for d in files if d.get("_path") == earlier["file"])
            keys_other = {
                (str(i.get("topic", "")), str(i.get("source_url", "")))
                for i in other.get("insights") or []
                if isinstance(i, dict)
            }
            for i in here.get("insights") or []:
                if not isinstance(i, dict):
                    continue
                key = (str(i.get("topic", "")), str(i.get("source_url", "")))
                if key not in keys_other:
                    continue
                if MARK_SUPERSEDED in i:
                    marked += 1
                else:
                    lost_keys += 1
        details.append(
            {
                "file": row["file"],
                "cycle": row["cycle"],
                "synced_at": row["synced_at"],
                "overwritten_by_fresher": lost_keys,
                "already_marked_superseded": marked,
            }
        )
        lost += lost_keys

    return {
        "files": rows,
        "inverted_files": [r["file"] for r in inverted_files],
        "inverted_count": len(inverted_files),
        "lost": lost,
        "lost_detail": details,
        "order_is_chronological": not inverted_files,
    }


# --- Происхождение --------------------------------------------------------

# Домены, которые для source_type == "textbook" означают подмену:
# учебник — это файл в vault, а не пост в соцсети.
_SOCIAL_HOSTS = ("x.com", "twitter.com", "facebook.com", "instagram.com",
                 "reddit.com", "youtube.com", "t.me", "telegram.me",
                 "vk.com", "ok.ru", "dzen.ru", "pikabu.ru", "habr.com")
# Мусорные темы от навигационного сканера: «X: <числовой id>».
_NAV_TOPIC_RE = None  # собирается без re, чтобы модуль оставался чистым


def _is_social(url: str) -> bool:
    low = url.lower()
    if not low:
        return False
    for host in _SOCIAL_HOSTS:
        if host in low:
            return True
    return False


def _is_vault_markdown(url: str) -> bool:
    return url.lower().endswith(".md") or ".md?" in url.lower()


def _is_nav_topic(topic: str) -> bool:
    """Тема вида `X: 2087163793558126997` — навигация, а не знание."""
    if not topic.startswith("X:"):
        return False
    tail = topic[2:].strip()
    return tail.isdigit()


def origin_findings(
    items: Iterable[Dict[str, Any]], skip_acknowledged: bool = True
) -> List[Dict[str, Any]]:
    """Записи с подменённым происхождением (список с причиной и местом).

    `skip_acknowledged` — не считать находкой запись, в которой эта причина
    уже записана (`origin_issue`, пункт 19). Иначе `--fix` не мог бы закрыть
    дефект: находка останется в отчёте и после того, как файл помечен.
    Причина помечается как решённая (список `reasons`), поэтому
    подтверждённая пометка и новая подмена — разные вещи.
    """
    findings: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", ""))
        url = str(item.get("source_url", "") or "")
        stype = str(item.get("source_type", "") or "")
        reasons: List[str] = []
        if stype == "textbook" and url and _is_social(url):
            reasons.append("source_type=textbook, но source_url — соцсеть")
        if stype == "textbook" and url and not _is_vault_markdown(url) and not _is_social(url):
            reasons.append("source_type=textbook, но source_url не ведёт в vault (.md)")
        if _is_nav_topic(topic):
            reasons.append("topic вида 'X: <id>' — навигация сканера, а не тема")
        if not reasons:
            continue
        if skip_acknowledged:
            already = item.get(MARK_ORIGIN)
            if isinstance(already, list) and set(already) >= set(reasons):
                continue
        findings.append(
            {
                "index": idx,
                "topic": topic,
                "source_url": url,
                "source_type": stype,
                "reasons": reasons,
            }
        )
    return findings


# --- Разметка устаревшего (`--fix`, пункт 19) ------------------------------


def stale_duplicates(files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Записи, которые уже представлены в более свежем файле.

    Для каждой такой записи известен источник свежести (файл, чья
    `synced_at` больше), поэтому пометка не выдумывает provenance — она
    называет конкретный файл, из которого запись пришла в виде дубля.
    """
    rows = file_order_report(files)
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not row["inverted"]:
            continue
        here = next(d for d in files if d.get("_path") == row["file"])
        here_fresh = row["freshness"]
        if here_fresh is None:
            continue
        for earlier in rows:
            if earlier["freshness"] is None or earlier["freshness"] <= here_fresh:
                continue
            other = next(d for d in files if d.get("_path") == earlier["file"])
            keys_other = {
                (str(i.get("topic", "")), str(i.get("source_url", "")))
                for i in other.get("insights") or []
                if isinstance(i, dict)
            }
            for idx, item in enumerate(here.get("insights") or []):
                if not isinstance(item, dict):
                    continue
                key = (str(item.get("topic", "")), str(item.get("source_url", "")))
                if key not in keys_other:
                    continue
                if MARK_SUPERSEDED in item:
                    continue
                out.append(
                    {
                        "file": row["file"],
                        "index": idx,
                        "topic": key[0],
                        "source_url": key[1],
                        "kind": "superseded",
                        "superseded_by": earlier["file"],
                        "superseded_by_synced_at": earlier["synced_at"],
                        "own_synced_at": row["synced_at"],
                    }
                )
    return out


def plan_freshness_fix(files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Что именно `--fix` собирается сделать: устаревшие дубли + происхождение.

    Ничего не применяет. Порядок важен: сначала разметка устаревших дублей
    (по файлам), затем находки происхождения — обе операции только добавляют
    поля, ни одну запись не удаляют.
    """
    plan = stale_duplicates(files)
    # Происхождение считаем ПОФАЙЛОВО: индексы origin_findings сквозные по
    # переданному потоку, а разметка адресована конкретной записи в
    # конкретном файле. Сквозной индекс здесь поставил бы пометку на
    # соседнюю тему другого файла.
    for data in files:
        own = [i for i in (data.get("insights") or []) if isinstance(i, dict)]
        by_index = {id(i): n for n, i in enumerate(own)}
        for finding in origin_findings(own):
            pos = by_index.get(id(own[finding["index"]]))
            if pos is None:
                continue
            plan.append(
                {
                    "kind": "origin",
                    "file": data.get("_path"),
                    "index": pos,
                    "topic": finding["topic"],
                    "source_url": finding["source_url"],
                    "reasons": finding["reasons"],
                }
            )
    return plan


def apply_freshness_fix(
    data: Dict[str, Any], plan: Sequence[Dict[str, Any]]
) -> Tuple[Dict[str, Any], int]:
    """Разметить записи файла по плану. Возвращает (новые данные, сколько помечено).

    Мутирует глубокие копии, а не загруженный объект: `load()` уже отдаёт
    разобранный JSON, и молчаливая правка его на месте сделала бы
    невоспроизводимым dry-run, который печатался до этого вызова.
    """
    import copy

    out = copy.deepcopy({k: v for k, v in data.items() if not k.startswith("_")})
    insights = out.get("insights") or []
    count = 0
    for step in plan:
        idx = step.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(insights):
            continue
        item = insights[idx]
        if not isinstance(item, dict):
            continue
        if step.get("kind") == "superseded":
            item[MARK_SUPERSEDED] = {
                "file": step.get("superseded_by"),
                "synced_at": step.get("superseded_by_synced_at"),
            }
        elif step.get("kind") == "origin":
            item[MARK_ORIGIN] = step.get("reasons") or []
        else:
            continue
        count += 1
    out["total_insights"] = len(insights)
    return out, count


# --- Константность полей --------------------------------------------------

PROFILE_FIELDS = (
    "category",
    "source_type",
    "relevance_score",
    "tags",
    "applicable_projects",
)


def _freeze(value: Any) -> Any:
    """Значение поля как ключ сравнения (списки — через кортеж)."""
    if isinstance(value, list):
        return ("list", tuple(str(v) for v in value))
    return str(value)


def field_profile(
    items: Iterable[Dict[str, Any]],
    fields: Sequence[str] = PROFILE_FIELDS,
    constant_share: float = CONSTANT_SHARE,
) -> List[Dict[str, Any]]:
    """Доля записей, делящих одно значение, по каждому полю."""
    rows: List[Dict[str, Any]] = []
    total = 0
    counter: Dict[str, Dict[Any, int]] = {f: {} for f in fields}
    for item in items:
        if not isinstance(item, dict):
            continue
        total += 1
        for field in fields:
            key = _freeze(item.get(field))
            counter[field][key] = counter[field].get(key, 0) + 1
    for field in fields:
        counts = counter[field]
        if not total:
            rows.append({"field": field, "distinct": 0, "top_share": 0.0, "constant": False,
                         "values": {}})
            continue
        top_value, top_n = max(counts.items(), key=lambda kv: (kv[1], str(kv[0])))
        share = top_n / total
        rows.append(
            {
                "field": field,
                "distinct": len(counts),
                "top_value": repr(top_value),
                "top_count": top_n,
                "top_share": round(share, 4),
                "constant": share >= constant_share,
                "values": {repr(k): v for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))},
            }
        )
    return rows


def relevance_informative(items: Iterable[Dict[str, Any]]) -> Tuple[bool, float]:
    """Различает ли relevance_score записи. Возвращает (да/нет, разброс).

    Пока поле принимает одно значение на корпусе, множитель
    `(0.5 + 0.5 * relevance)` в ранжировании постоянен и не влияет ни на
    один порядок. Это надо называть, а не выдавать за вклад в оценку.
    """
    values: List[float] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = item.get("relevance_score")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        values.append(float(raw))
    if len(values) < 2:
        return False, 0.0
    lo, hi = min(values), max(values)
    return (hi - lo) > 1e-12, round(hi - lo, 6)


def consolidate_insights(
    items: Iterable[Dict[str, Any]],
    file_freshness_map: Optional[Dict[str, Optional[float]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Полная очистка корпуса: мусор → дедуп по свежести.

    `clean_insights()` оставляет первый встреченный дубль, а это позиция
    в списке файлов, то есть номер цикла из имени. Здесь порядок заменён
    доказуемым: побеждает запись с бо́льшим `timestamp`, а без даты —
    `synced_at` содержащего её файла. Мусор отбрасывается первым, чтобы
    запись `Unknown` не вытесняла нормальную копию того же ключа.

    Возвращает (список, статистика с полями `junk`, `duplicates`,
    `replaced`, `stale_wins`, `undated_wins`, `unparsable`, `kept`).
    """
    from .validate import clean_insights

    rows = list(items)
    fresh_map = file_freshness_map or {}

    def fallback_for(item: Dict[str, Any]) -> Optional[float]:
        name = str(item.get("_file", ""))
        for path, fresh in fresh_map.items():
            if str(path).endswith(name):
                return fresh
        return None

    prepared: List[Dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict) and item.get("timestamp") in (None, ""):
            fb = fallback_for(item)
            if fb is not None:
                item = dict(item)
                item["timestamp"] = item.get("_synced_at") or None
                if item["timestamp"] is None:
                    del item["timestamp"]
                item["_freshness_fallback"] = fb
        prepared.append(item)

    kept, stats = clean_insights(prepared)
    # Второй проход — дедуп по свежести уже среди не-мусорных записей.
    fresh_by_item: Dict[int, Optional[float]] = {}
    for pos, item in enumerate(prepared):
        if isinstance(item, dict) and item.get("_freshness_fallback") is not None:
            fresh_by_item[id(item)] = item["_freshness_fallback"]

    kept2, dedupe_stats = dedupe_by_freshness(
        kept,
        fallback=None,
    )
    # Для записей без собственного timestamp подставляем свежесть файла.
    if any(v is not None for v in fresh_by_item.values()):
        repaired: List[Dict[str, Any]] = []
        for item in kept:
            if parse_ts(item.get("timestamp")) is None:
                fb = fresh_by_item.get(id(item))
                if fb is not None:
                    clone = dict(item)
                    clone["_freshness_fallback"] = fb
                    repaired.append(clone)
                    continue
            repaired.append(item)
        kept3, dedupe_stats = dedupe_by_freshness(
            _with_fallback(repaired),
            fallback=None,
        )
    else:
        kept3 = kept2

    out = [
        {k: v for k, v in item.items() if not k.startswith("_freshness_fallback")}
        for item in kept3
    ]
    stats["replaced"] = dedupe_stats["replaced"]
    stats["stale_wins"] = dedupe_stats["stale_wins"]
    stats["undated_wins"] = dedupe_stats["undated_wins"]
    stats["unparsable"] = dedupe_stats["unparsable"]
    stats["kept"] = len(out)
    return out, stats


def _with_fallback(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Подставить `_freshness_fallback` как timestamp, если своего нет."""
    out: List[Dict[str, Any]] = []
    for item in items:
        fb = item.get("_freshness_fallback")
        if parse_ts(item.get("timestamp")) is None and fb is not None:
            from datetime import datetime, timezone

            clone = dict(item)
            clone["timestamp"] = datetime.fromtimestamp(fb, tz=timezone.utc).isoformat()
            out.append(clone)
        else:
            out.append(item)
    return out