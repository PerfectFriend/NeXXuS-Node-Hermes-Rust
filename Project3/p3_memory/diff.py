"""Дифф циклов памяти (фаза 3, пункт 24 плана).

Сравнивает два цикла по каноническому ключу записи (``canon.record_key``)
и отвечает: что добавилось, что пропало, что изменилось (какие поля),
а что стоит на месте. Служебные поля ``_…`` (те, что кладёт ``loader``)
в изменение не считаются; сравнение строк идёт через ``normalize_text``,
у URL дополнительно срезается query/хвост и завершающий «/», чтобы
технический мусор не выглядел правкой.

Ничего на диск не пишет.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .canon import normalize_text, record_key
from .loader import DEFAULT_DIR, MemoryInvalid, discover, load

_CYCLE_RE = re.compile(r"cycle_(\d+)\.json$")

#: Поля, которые меняются сами по себе и правкой содержания не являются.
#:
#: Живая проверка фазы 3 (2026-10-04) дала 85 «изменённых» записей между
#: циклами 001 и 1351 — и все 85 отличались **только** полем
#: `timestamp`. Содержание не тронуто: записи те же, просто перезаписаны
#: на следующем проходе. Считать это правкой памяти нельзя — иначе отчёт
#: говорит «память переписывают» там, где переписали только отметку
#: времени. Тот же класс, что закрыл пункт 13 для соседей
#: (`identity.SERVICE_FIELDS`): технический шум не характеризует правку.
#:
#: Список намеренно узкий. Любое другое поле — правка, даже если оно
#: выглядит служебным: сузить список — можно, выдать шум за правку —
#: нет.
VOLATILE_FIELDS = ("timestamp",)


def cycle_number(name: str) -> Optional[int]:
    """Номер цикла из имени файла (``professor_insights_cycle_1351.json`` → 1351)."""
    match = _CYCLE_RE.search(Path(name).name)
    return int(match.group(1)) if match else None


def pick_default_pair(memory_dir: Path = DEFAULT_DIR) -> Tuple[Path, Path]:
    """Два последних цикла: (предыдущий, последний).

    Сортировка — по номеру цикла, а не по имени файла: поимённо
    ``cycle_0999`` стоит раньше ``cycle_100``, а по номеру нет.
    """
    files = discover(memory_dir)
    if len(files) < 2:
        raise MemoryInvalid(
            f"{memory_dir}: для diff нужно минимум 2 цикла, найдено {len(files)}"
        )
    ordered = sorted(files, key=lambda p: (cycle_number(p.name) or 0, p.name))
    return ordered[-2], ordered[-1]


def resolve_cycle(memory_dir: Path, ref: str) -> Path:
    """Приёмает число цикла (с любой ведущей прошивкой нулями),
    имя файла или путь к файлу."""
    memory_dir = Path(memory_dir)
    direct = memory_dir / ref
    if direct.is_file():
        return direct
    if Path(ref).suffix == "":
        candidate = memory_dir / f"professor_insights_cycle_{ref}.json"
        if candidate.is_file():
            return candidate
    if ref.isdigit():
        number = int(ref)
        for path in discover(memory_dir):
            if cycle_number(path.name) == number:
                return path
    raise MemoryInvalid(f"{ref}: файл цикла не найден в {memory_dir}")


def record_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """Поля записи без служебных ``_…``."""
    return {k: v for k, v in record.items() if not str(k).startswith("_")}


def _norm_url(url: Any) -> str:
    text = normalize_text(url)
    return text.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def _norm_value(field: str, value: Any) -> Any:
    if field == "source_url":
        return _norm_url(value) if value is not None else None
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [_norm_value(field, item) for item in value]
    return value


def changed_fields(
    old: Dict[str, Any], new: Dict[str, Any]
) -> List[str]:
    """Имена полей, изменившихся между двумя версиями одной записи."""
    fields: List[str] = []
    for name in sorted(set(old) | set(new)):
        if _norm_value(name, old.get(name)) != _norm_value(name, new.get(name)):
            fields.append(name)
    return fields


def substantive_fields(
    old: Dict[str, Any], new: Dict[str, Any]
) -> List[str]:
    """Поля с содержательной правкой — всё, кроме ``VOLATILE_FIELDS``.

    Смена одного только неустойчивого поля содержательной правки не
    является: запись та же, перезаписан лишь отметка времени.
    """
    return [name for name in changed_fields(old, new)
            if name not in VOLATILE_FIELDS]


def _view(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic": record.get("topic"),
        "category": record.get("category"),
        "source_url": record.get("source_url"),
    }


def _is_moved(old_record: Dict[str, Any], new_records: Iterable[Dict[str, Any]]) -> bool:
    """Запись сменила категорию, но не пропала.

    Ключ дедупликации — тема + категория + URL (`canon.record_key`), так
    что смена одной только категории меняет ключ, и в диффе запись
    выглядит как удалённая плюс добавленная. Это ложное удаление: она
    никуда не девалась, а переехала в другую категорию. Переезд
    отличаем по совпадению URL и темы при другой категории.
    """
    url = _norm_url(old_record.get("source_url"))
    if url is None:
        return False
    topic = normalize_text(old_record.get("topic"))
    old_category = _norm_value("category", old_record.get("category"))
    for candidate in new_records:
        if _norm_url(candidate.get("source_url")) != url:
            continue
        if normalize_text(candidate.get("topic")) != topic:
            continue
        if _norm_value("category", candidate.get("category")) != old_category:
            return True
    return False


def group_by_key(
    data: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """Записи цикла, сгруппированные по каноническому ключу.

    Ключ — не уникальный идентификатор записи, а признак дедупликации:
    одна и та же пара «тема + категория + URL» может встречаться в
    цикле несколько раз (в штатном корпусе ключ ``unknown|ai
    engineering|`` встречается дважды в цикле 001 и трижды в 1351).
    Складывать записи в ``dict[key] = record`` нельзя: последний
    экземпляр затирает предыдущие, и кратность молча теряется. Раньше
    из 102 записей цикла 001 в расчёт попадало 101, а из 88 записей
    1351 — 86, и равенства «удалено + переехало + общее = было
    записей» не сходились ни на одной стороне.

    Поэтому по ключу хранится **список**: сравнение ведётся как
    мультимножество, лишние экземпляры попадают в ``added``/``removed``,
    а общие — сравниваются попарно.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in data.get("insights") or []:
        groups.setdefault(record_key(record), []).append(record_fields(record))
    return groups


def diff_cycles(
    data_from: Dict[str, Any], data_to: Dict[str, Any]
) -> Dict[str, Any]:
    """Сравнить два загруженных цикла (списки ``insights``).

    Сравнение ведётся как мультимножество: один и тот же канонический
    ключ может встретиться в цикле несколько раз, и кратность должна
    сохраниться в обе стороны — иначе расчёт «удалено + переехало +
    общее = было записей» не сходится (см. ``group_by_key``).
    """
    old = group_by_key(data_from)
    new = group_by_key(data_to)

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    moved: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    rewritten: List[Dict[str, Any]] = []
    unchanged = 0
    for key, new_records in new.items():
        old_records = old.get(key)
        if not old_records:
            # Ключ новый целиком — либо действительно новая запись, либо
            # лишний экземпляр уже известного ключа: у нового цикла
            # их больше, чем у старого. Для читателя это одно и то же
            # («появилась запись»), и прятать различие незачем.
            added.extend(_view(record) for record in new_records)
            continue
        # Кратности сравниваем попарно: первый экземпляр против
        # первого, второй против второго, и так далее. Лишние с любой
        # стороны считаем появлением/пропажей, а не затиранием.
        for old_record, new_record in zip(old_records, new_records):
            fields = changed_fields(old_record, new_record)
            if not fields:
                unchanged += 1
                continue
            substantive = [name for name in fields if name not in VOLATILE_FIELDS]
            if substantive:
                changed.append({"topic": new_record.get("topic"), "fields": fields})
            else:
                # Отметка времени сменилась, содержание нет: это перезапись,
                # а не правка. Реестр урезать нельзя — молчаливое исчезновение
                # 85 записей из отчёта было бы не менее ложью, чем ложное
                # «изменено».
                rewritten.append({"topic": new_record.get("topic"), "fields": fields})
        added.extend(_view(record) for record in new_records[len(old_records):])
    for key, old_records in old.items():
        new_records = new.get(key)
        if not new_records:
            # Пропала или переехала: ключ дедупликации включает
            # `category`, поэтому смена категории сама по себе выглядит
            # как удаление. Считать это пропажей нельзя — читатель увидит
            # потерю записи там, где её лишь переложили в другую рубрику.
            # Искать переезд надо по **всем** новым записям, а не только
            # по тем, чей ключ совпал: переехавшая запись стоит уже под
            # другим ключом.
            new_all = [record for records in new.values() for record in records]
            for old_record in old_records:
                if _is_moved(old_record, new_all):
                    moved.append(_view(old_record))
                else:
                    removed.append(_view(old_record))
            continue
        # У нового цикла таких записей меньше — лишние старые экземпляры
        # пропали. Переезд для них проверяем отдельно, а то лишний дубль
        # засчитался бы пропажей там, где его на самом деле не стало.
        removed_any = old_records[len(new_records):]
        new_all = [record for records in new.values() for record in records]
        for old_record in removed_any:
            if _is_moved(old_record, new_all):
                moved.append(_view(old_record))
            else:
                removed.append(_view(old_record))

    return {
        "from_file": data_from.get("_source_file"),
        "to_file": data_to.get("_source_file"),
        "from_cycle": data_from.get("cycle"),
        "to_cycle": data_to.get("cycle"),
        "from_records": len(data_from.get("insights") or []),
        "to_records": len(data_to.get("insights") or []),
        "added": added,
        "removed": removed,
        "moved": moved,
        "changed": changed,
        "rewritten": rewritten,
        "unchanged": unchanged,
        "shared": unchanged + len(changed) + len(rewritten),
    }


def cycle_coverage(memory_dir: Path = DEFAULT_DIR) -> Dict[str, Any]:
    """Покрытие циклов (фаза 3, пункт 26): какие циклы есть, сколько в них
    записей, где в нумерации разрывы и как меняется число записей."""
    memory_dir = Path(memory_dir)
    files = discover(memory_dir)
    cycles: List[Dict[str, Any]] = []
    for path in sorted(files, key=lambda p: (cycle_number(p.name) or 0, p.name)):
        data = load(path)
        cycles.append({
            "file": path.name,
            "file_cycle": cycle_number(path.name),
            "cycle_field": data.get("cycle"),
            "records": len(data.get("insights") or []),
        })
    numbers = sorted({c["file_cycle"] for c in cycles
                      if c["file_cycle"] is not None})
    gaps = [[low + 1, high - 1] for low, high in zip(numbers, numbers[1:])
            if high - low > 1]
    deltas = [{
        "from": prev["file"],
        "to": cur["file"],
        "records_delta": cur["records"] - prev["records"],
    } for prev, cur in zip(cycles, cycles[1:])]
    return {
        "memory_dir": str(memory_dir),
        "cycles": cycles,
        "numbering_gaps": gaps,
        "record_deltas": deltas,
        "first_cycle": numbers[0] if numbers else None,
        "last_cycle": numbers[-1] if numbers else None,
    }


def diff(
    memory_dir: Path = DEFAULT_DIR,
    ref_from: Optional[str] = None,
    ref_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Дифф двух циклов из каталога памяти.

    Без аргументов берёт два последних цикла (см. ``pick_default_pair``).
    """
    memory_dir = Path(memory_dir)
    if ref_from is None or ref_to is None:
        first, second = pick_default_pair(memory_dir)
        ref_from = ref_from or first.name
        ref_to = ref_to or second.name
    path_from = resolve_cycle(memory_dir, ref_from)
    path_to = resolve_cycle(memory_dir, ref_to)
    result = diff_cycles(load(path_from), load(path_to))
    result["memory_dir"] = str(memory_dir)
    return result


def _entry_line(kind: str, entry: Dict[str, Any]) -> str:
    """Строка перечня: вид перехода и **кто именно** в него попал.

    Голых чисел мало: «удалено 16» не отвечает на вопрос «что именно
    пропало». Поэтому называем тему, категорию и URL — тем же
    `_view`, что и в JSON-выводе, чтобы сводка и машина показывали
    одно и то же.
    """
    topic = entry.get("topic") or "(без темы)"
    category = entry.get("category") or "(без категории)"
    url = entry.get("source_url") or "(без URL)"
    fields = entry.get("fields")
    tail = f" — поля: {', '.join(fields)}" if fields else ""
    return f"  [{kind}] {topic} / {category} / {url}{tail}"


def diff_text(result: Dict[str, Any], limit: int = 20) -> str:
    """Человеческая сводка диффа (для CLI без ``--json``).

    Перечисляет все пять видов перехода, а не только правки: иначе
    читатель видит «добавлено: 2, удалено: 16» и не знает, о каких
    именно записях речь. Каждый вид ограничен ``limit`` строками, но
    общее число печатается всегда — иначе сокращение неотличимо от
    отсутствия записей.
    """
    lines = [
        f"diff циклов: {result['from_cycle']} → {result['to_cycle']}",
        f"откуда: {result['from_file']} ({result['from_records']} записей)",
        f"куда:   {result['to_file']} ({result['to_records']} записей)",
        (
            f"добавлено: {len(result['added'])}, "
            f"удалено: {len(result['removed'])}, "
            f"изменено: {len(result['changed'])}, "
            f"без изменений: {result['unchanged']}"
        ),
    ]
    # Переезды и перезаписи — отдельные виды: иначе «переехало» не
    # отличимо от «пропало», а «перезаписано» — от правки. Раньше обе
    # категории в сводку вообще не попадали.
    for key, kind in (("removed", "удал"), ("moved", "переех"),
                      ("added", "добав"), ("changed", "изм"),
                      ("rewritten", "перезаписан")):
        entries = result.get(key) or []
        if not entries:
            continue
        lines.append(f"{kind}: {len(entries)}")
        for entry in entries[:limit]:
            lines.append(_entry_line(kind, entry))
        if len(entries) > limit:
            lines.append(f"  … ещё {len(entries) - limit}")
    # Сходимость видна читателю, а не только тесту: если равенства
    # разошлись, значит инструмент врёт, и об этом сказано словами.
    balance = (
        len(result["removed"]) + len(result["moved"]) + result["shared"],
        len(result["added"]) + len(result["moved"]) + result["shared"],
        result["from_records"], result["to_records"],
    )
    if balance[0] != balance[2] or balance[1] != balance[3]:
        lines.append(
            "ВНИМАНИЕ: сходимость нарушена — "
            f"старая сторона {balance[0]} против {balance[2]}, "
            f"новая {balance[1]} против {balance[3]} записей"
        )
    return "\n".join(lines)
