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
from typing import Any, Dict, List, Optional, Tuple

from .canon import normalize_text, record_key
from .loader import DEFAULT_DIR, MemoryInvalid, discover, load

_CYCLE_RE = re.compile(r"cycle_(\d+)\.json$")


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


def _view(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic": record.get("topic"),
        "category": record.get("category"),
        "source_url": record.get("source_url"),
    }


def diff_cycles(
    data_from: Dict[str, Any], data_to: Dict[str, Any]
) -> Dict[str, Any]:
    """Сравнить два загруженных цикла (списки ``insights``)."""
    old: Dict[str, Dict[str, Any]] = {}
    for record in data_from.get("insights") or []:
        old[record_key(record)] = record_fields(record)
    new: Dict[str, Dict[str, Any]] = {}
    for record in data_to.get("insights") or []:
        new[record_key(record)] = record_fields(record)

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    unchanged = 0
    for key in new:
        if key not in old:
            added.append(_view(new[key]))
            continue
        fields = changed_fields(old[key], new[key])
        if fields:
            changed.append({"topic": new[key].get("topic"), "fields": fields})
        else:
            unchanged += 1
    for key in old:
        if key not in new:
            removed.append(_view(old[key]))

    return {
        "from_file": data_from.get("_source_file"),
        "to_file": data_to.get("_source_file"),
        "from_cycle": data_from.get("cycle"),
        "to_cycle": data_to.get("cycle"),
        "from_records": len(data_from.get("insights") or []),
        "to_records": len(data_to.get("insights") or []),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "shared": unchanged + len(changed),
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


def diff_text(result: Dict[str, Any], limit: int = 20) -> str:
    """Человеческая сводка диффа (для CLI без ``--json``);
    перечень изменений сокращает ``limit`` строк."""
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
    for entry in result["changed"][:limit]:
        lines.append(
            f"  [изм] {entry['topic']} — поля: {', '.join(entry['fields'])}"
        )
    if len(result["changed"]) > limit:
        lines.append(f"  … ещё {len(result['changed']) - limit} изменений")
    return "\n".join(lines)
