"""Харнесс-тест реального прогона professor_sync.py → память Project1.

Зачем. Пункт 11 плана Project1: измерить фактическое число инсайтов и
долю мусора в свежей памяти, а не читать код. Код скрипта — чужой
hot-код, поэтому он не правится: харнесс подменяет только корни
(запись идёт в песочницу), а сам `ProfessorSync` — настоящий.

Измеряется на выходе реального вызова:
- сколько инсайтов записано и сколько было на входе;
- доля мусора (`topic == "Unknown"` / пустой summary);
- дубликаты `(topic, source_url)`;
- валидность JSON после записи (проверка загрузчиком Project1);
- отработал ли git-коммит внутри скрипта.

Запуск:  python3 harness_sync_run.py
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LIVINGCODE = Path("/home/thomas/LivingCode")
PROJECT1 = LIVINGCODE / "Project1"
SCRIPT = LIVINGCODE / "scripts" / "professor_sync.py"

# Тестовый цикл заведомо не совпадает с рабочими (1 и 1351) и с
# автоопределением, чтобы файл памяти в песочнице был узнаваем.
CYCLE = 990001


def load_sync_module():
    """Загрузить professor_sync.py как модуль, не импортируя из scripts/."""
    spec = importlib.util.spec_from_file_location("professor_sync_probe", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"не удалось загрузить {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_sandbox(tmp: Path) -> Path:
    """Песочница с копией Project1 и собственным git-репозиторием."""
    root = tmp / "LivingCode"
    proj = root / "Project1"
    proj.mkdir(parents=True)
    for name in ("memory",):
        src = PROJECT1 / name
        if src.is_dir():
            shutil.copytree(src, proj / name)
    chronicle = PROJECT1 / "CHRONICLE.md"
    if chronicle.is_file():
        shutil.copy2(chronicle, proj / "CHRONICLE.md")

    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.email", "harness@local"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.name", "harness"], cwd=str(root), check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "песочница: состояние до прогона"],
        cwd=str(root), check=True,
    )
    return root


def main() -> int:
    module = load_sync_module()

    # Дополнительный проект, чтобы проверить фильтр applicable_projects:
    # синхронизация шла только в Project1, значит и появиться он должен
    # только там.
    tmp = Path(tempfile.mkdtemp(prefix="p1harness-"))
    root = make_sandbox(tmp)
    print(f"песочница: {root}")

    sync = module.ProfessorSync(CYCLE)
    vault = sync.vault_root
    print(f"vault_root скрипта: {vault}  (существует: {vault.is_dir()})")
    print(f"textbook скрипта: {sync.textbook_path}  (существует: {sync.textbook_path.is_file()})")

    # --- единственное место подмены: корни -----------------------------
    sync.root = root

    before = {p.name for p in (root / "Project1" / "memory").glob("*.json")}
    insights = sync.load_textbook_insights()
    print(f"\nпрочитано инсайтов из источников: {len(insights)}")

    relevant = [i for i in insights if 1 in i.applicable_projects]
    print(f"подходит для Project1: {len(relevant)}")

    result = sync.sync_to_project(1, insights)
    print(f"\nрезультат sync_to_project: {json.dumps(result, ensure_ascii=False)}")

    # --- измеряем выход -------------------------------------------------
    mem_dir = root / "Project1" / "memory"
    after = {p.name for p in mem_dir.glob("*.json")}
    new_files = sorted(after - before)
    print(f"\nновые файлы в памяти: {new_files or 'НЕТ'}")
    print(f"файлы в Project2 (не должен появляться): "
          f"{sorted(p.name for p in (root / 'Project2').glob('**/*.json')) if (root / 'Project2').exists() else 'Project2 не создан'}")

    target = mem_dir / f"professor_insights_cycle_{CYCLE:03d}.json"
    measured = {}
    if not target.is_file():
        print(f"\nОШИБКА: ожидаемый файл не создан: {target}")
        return 1

    raw = target.read_text(encoding="utf-8")
    measured["size_bytes"] = len(raw)
    try:
        doc = json.loads(raw)
        measured["json_valid"] = True
    except json.JSONDecodeError as exc:
        measured["json_valid"] = False
        print(f"\nОШИБКА: JSON невалиден: {exc}")
        return 1

    items = doc.get("insights", [])
    junk = [
        i for i in items
        if (i.get("topic") or "Unknown") == "Unknown" or not (i.get("summary") or "").strip()
    ]
    keys = Counter((i.get("topic"), i.get("source_url")) for i in items)
    dupes = [k for k, c in keys.items() if c > 1]
    no_url = [i for i in items if not (i.get("source_url") or "").strip()]

    measured.update({
        "cycle": doc.get("cycle"),
        "total_insights_declared": doc.get("total_insights"),
        "total_insights_factual": len(items),
        "junk": len(junk),
        "junk_share": round(100.0 * len(junk) / len(items), 2) if items else 0.0,
        "duplicate_keys": len(dupes),
        "without_source_url": len(no_url),
    })

    # сверка declared против факта — тот самый класс дефекта, который
    # validate.py ловит в Project1
    measured["declared_matches_factual"] = (
        measured["total_insights_declared"] == measured["total_insights_factual"]
    )

    # --- проверка загрузчиком Project1 ----------------------------------
    sys.path.insert(0, str(PROJECT1))
    from p1_memory.loader import MemoryError_, load
    from p1_memory.validate import validate_document
    try:
        loaded = load(target)
        measured["p1_loader_ok"] = True
        measured["p1_schema_problems"] = len(validate_document(loaded))
    except MemoryError_ as exc:
        measured["p1_loader_ok"] = False
        measured["p1_loader_error"] = str(exc)

    # --- git-коммит внутри скрипта --------------------------------------
    log = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=str(root),
        capture_output=True, text=True,
    )
    measured["git_commit_in_script"] = log.stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(root), capture_output=True, text=True,
    )
    measured["git_clean_after_run"] = not dirty.stdout.strip()

    chronicle = root / "Project1" / "CHRONICLE.md"
    measured["chronicle_grew_bytes"] = (
        chronicle.stat().st_size - (PROJECT1 / "CHRONICLE.md").stat().st_size
    )

    # --- сводка ----------------------------------------------------------
    print("\n" + "=" * 68)
    print("ИЗМЕРЕНО РЕАЛЬНЫМ ПРОГОНОМ")
    print("=" * 68)
    for key, value in measured.items():
        print(f"  {key:32s} {value}")

    out = tmp / "harness_result.json"
    out.write_text(json.dumps(measured, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON-замер сохранён: {out}")
    print(f"песочница сохранена для разбора: {tmp}")

    ok = measured["json_valid"] and measured["p1_loader_ok"] and measured["declared_matches_factual"]
    print("\nИТОГ: " + ("прогон корректен" if ok else "ЕСТЬ ПРОБЛЕМЫ"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())