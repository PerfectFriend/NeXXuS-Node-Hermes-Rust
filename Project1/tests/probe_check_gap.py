"""Проба: ловит ли `report --check` расхождение чисел ВНЕ таблицы.

Дефект-кандидат фазы 4: freshness.check_report сверяет только markdown-таблицу
(всего/мусор/дубли/чистых по файлам) и число тестов. Всё остальное, что отчёт
утверждает текстом — 84 кросс-файловых дубля, 100 оставшихся, 190 входа,
provenance-факты (184 записи = [1,2,3,4], relevance 0.9) — не сверяется ни с
чем. Если такое число протухнет, отчёт молча разойдётся с прогоном.

Честная граница решения (её же сформулировал пункт 21 плана): «число вне
маркера текстом не считается числом». Значит произвольную правку числа в
обычном тексте сверка поймать НЕ ОБЯЗАНА — иначе пришлось бы знать смысл
каждой фразы отчёта. Обязана она ровно одно:

  * блок фактов сверить с прогоном (этап 2b) — подмена 84→7 и 100→77
    ОБЯЗАНА дать ok=False с перечислением расхождений;
  * а если блока нет вовсе (отчёт не переведён) — это само по себе
    расхождение (этап 1), а не тихий зелёный.

Этап 1 проверяет ровно это: на отчёте без блока сверка обязана быть не-ok.

Запуск: python3 probe_check_gap.py
"""

import re
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT1 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT1))

from p1_memory.freshness import check_report, stamp_facts  # noqa: E402


def _fresh_tree() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="p1probe-"))
    root = tmp / "Project1"
    root.mkdir(parents=True)
    shutil.copytree(PROJECT1 / "memory", root / "memory")
    shutil.copytree(PROJECT1 / "tests", root / "tests")
    shutil.copy2(PROJECT1 / "MEMORY_REPORT.md", root / "MEMORY_REPORT.md")
    return root


def strip_facts(text: str) -> str:
    """Убрать блок фактов целиком (проверка контракта «нет блока = расхождение»)."""
    from p1_memory.freshness import _FACT_BLOCK_CLOSE, _FACT_BLOCK_OPEN

    if _FACT_BLOCK_OPEN not in text:
        return text
    head, _, rest = text.partition(_FACT_BLOCK_OPEN)
    _, _, tail = rest.partition(_FACT_BLOCK_CLOSE)
    return head + tail.lstrip("\n")


def stage_missing_block(root: Path) -> bool:
    """Отчёт без блока фактов обязан давать ok=False, а не тихий зелёный.

    Заодно портим числа в обычном тексте: по контракту пункта 21 сверка их
    не обязана ловить (знать смысл каждой фразы она не может), но отсутствие
    блока обязано быть расхождением само по себе.
    """
    report = root / "MEMORY_REPORT.md"
    text = strip_facts(report.read_text(encoding="utf-8"))
    patched, n = re.subn(r"84 записи повторяются", "7 записей повторяются", text)
    assert n == 1, f"подмена не сработала: {n}"
    patched = patched.replace("остаётся 100", "остаётся 77")
    report.write_text(patched, encoding="utf-8")
    result = check_report(root)
    print("этап 1 — блок фактов снят, числа в тексте подменены:")
    print(f"  ok = {result['ok']}  (ожидается False)")
    print(f"  facts_missing = {len(result['facts_missing'])} ключей (ожидается > 0)")
    return (not result["ok"]) and bool(result["facts_missing"])


def stage_fact_numbers(root: Path) -> bool:
    """Ставим настоящие факты, потом подменяем ОДНО из них в блоке."""
    report = root / "MEMORY_REPORT.md"
    from p1_memory.freshness import live_facts

    facts = live_facts(root)
    text = report.read_text(encoding="utf-8")
    text = stamp_facts(text, facts)
    report.write_text(text, encoding="utf-8")

    ok_ref = check_report(root)
    print("этап 2a — блок фактов совпадает с прогоном:")
    print(f"  ok = {ok_ref['ok']}  (ожидается True)")
    if not ok_ref["ok"]:
        print(f"  !! ok=False, но блок фактов чист; прочие расхождения:")
        for key in ("files_missing_in_report", "files_unknown_to_report",
                    "row_mismatches", "total_mismatches", "test_count_mismatches"):
            print(f"     {key} = {ok_ref[key]}")
        return False

    text = text.replace(
        f"<!-- p1-fact: cross_file_duplicates = {facts['cross_file_duplicates']} -->",
        "<!-- p1-fact: cross_file_duplicates = 7 -->",
    ).replace(
        f"<!-- p1-fact: cross_kept = {facts['cross_kept']} -->",
        f"<!-- p1-fact: cross_kept = {facts['cross_kept'] - 23} -->",
    )
    report.write_text(text, encoding="utf-8")
    result = check_report(root)
    print("этап 2b — то же число подменено 84→7 и 100→77, но УЖЕ В БЛОКЕ ФАКТОВ:")
    print(f"  ok = {result['ok']}")
    for row in result["fact_mismatches"]:
        print(f"  ! факт {row['fact']}: в отчёте {row['report']}, в прогоне {row['live']}")
    return not result["ok"]


def main() -> int:
    missing_block_caught = stage_missing_block(_fresh_tree())
    facts_caught = stage_fact_numbers(_fresh_tree())
    print()
    if missing_block_caught and facts_caught:
        print("OK: сверка ловит и отсутствие блока фактов, и подмену числа в нём")
        return 0
    print("ДЕФЕКТ НЕ ЗАКРЫТ: расхождение осталось незамеченным")
    return 1


if __name__ == "__main__":
    sys.exit(main())
