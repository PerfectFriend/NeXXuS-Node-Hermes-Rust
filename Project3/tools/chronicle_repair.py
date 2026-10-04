#!/usr/bin/env python3
"""Разовое исправление CHRONICLE.md: снятие маркера и удаление дубликата блока.

Скрипт создан в рамках пункта 27 плана (аудит хроники). Он читает файл,
находит точный повтор блока между двумя одинаковыми заголовками `## `
и удаляет копию, затем снимает строки-маркеры LivingCode из начала файла.
Работает идемпотентно: если дефектов нет, файл не меняется (--check-режим).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def find_duplicate_block(lines: list[str]) -> tuple[int, int] | None:
    """Найти диапазон (start, end) дубликата: 0-based, half-open.

    Ищем две одинаковые строки-заголовка `## `. Если блок между ними
    (до следующего разделителя `---`) совпадает побайтно — это дубликат.
    """
    idx = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    for a, b in zip(idx, idx[1:]):
        head = lines[a]
        # Конец блока a — следующая разделительная линия или следующий заголовок.
        end_a = b
        for j in range(a + 1, end_a):
            if lines[j].strip() == "---":
                end_a = j
                break
        if lines[a:end_a] == lines[b:b + (end_a - a)]:
            # Удаляем блок b вместе с разделителем перед ним.
            start_del = b
            if start_del - 1 >= 0 and lines[start_del - 1].strip() == "---":
                start_del -= 1
            return start_del, b + (end_a - a)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="починка CHRONICLE.md")
    ap.add_argument("path", help="путь к CHRONICLE.md")
    ap.add_argument("--apply", action="store_true", help="внести правки (по умолчанию только отчёт)")
    args = ap.parse_args(argv)

    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    markers = 0
    while markers < len(lines) and lines[markers].strip() in ("# HOT", "# COLD"):
        markers += 1

    dup = find_duplicate_block(lines)
    problems = []
    if markers:
        problems.append(f"маркеры в начале файла: {markers}")
    if dup:
        problems.append(f"дубликат блока: строки {dup[0] + 1}-{dup[1]}")
    if not problems:
        print(f"хроника чистая: {path}")
        return 0

    for problem in problems:
        print(f"  - {problem}")
    if not args.apply:
        return 1

    if dup:
        del lines[dup[0]:dup[1]]
    if markers:
        del lines[:markers]
    path.write_text("".join(lines), encoding="utf-8")
    print(f"починено: {path} ({len(lines)} строк)")
    return 0


if __name__ == "__main__":
    sys.exit(main())