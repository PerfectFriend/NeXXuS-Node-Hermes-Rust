"""Диагностика целостности исходников Project1.

Зачем этот модуль. В начале слота 2026-10-03 11:01 файл `chronicle.py`
оказался повреждён: в docstring попал NUL-байт, обрыв текста на ~560 байт
и посторонняя служебная строка. Python такой файл не импортирует —
`unittest` падал с `SyntaxError: source code string cannot contain null bytes`,
и весь пакет `p1_memory` становился недоступен целиком: 12 тестов к
Chronicle и 49 остальных не запускались вообще.

Причина та же, что и у маркер-скрипта: правку файла делал инструмент
записи, а повреждение замечали только при запуске. Класс дефекта —
«молчаливая порча исходника, не видимая до запуска».

Что делает модуль:

1. `scan_file()` — проверяет один файл: NUL-байты, бинарный мусор,
   служебные хвосты LLM-конвейера (строка целиком из обрывка потока),
   обрыв файла (последняя строка не завершена).
2. `compile_check()` — реальная компиляция каждого `.py` через
   `compile()`, потому что чтение текста ловит не всё, что ловит
   компилятор.
3. `scan_tree()` — то же по дереву проекта.
4. `is_blocking()` — отделяет порчу от предупреждений.
5. Команда CLI `doctor`: exit 1, если найдена порча.

Про границу правил. Служебный хвост распознаётся ТОЛЬКО если целая строка
состоит из мусора (с коротким хвостом-префиксом из 1–3 символов). Упоминание
этой строки в обычном тексте — например, в этом docstring — совпадением не
считается: иначе правило задевало бы само себя. Проверено на живой порче
`chronicle.py`, где строка была вида «п.Threading is disabled for this
response.» — префикс из двух символов, ничего больше.

Про «обрыв». Это единственное правило без блокирующей силы. Инструмент
записи в этой среде штатно срезает завершающий перевод строки, поэтому
признак встречается и на совершенно целых файлах. Он остаётся в отчёте
как подсказка, но не роняет exit-код: настоящий обрыв хватает правило
«синтаксис», потому что обрезанный файл не разбирается.

Модуль ничего не чинит и не пишет: он только диагностирует. Восстановление
источника — через git (`git checkout -- <путь>`), потому что только git
знает правильное состояние.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, NamedTuple

# Служебный хвост LLM-конвейера, попавший в исходник вместо текста.
# Весь мусор должен занимать строку целиком; хвост в квадратных/круглых
# скобках или с текстом после — это уже упоминание, а не порча.
JUNK_LINE_RE = re.compile(r"^.{0,3}Threading is disabled for this response\.?$")

SOURCE_DIRS = ("p1_memory", "tests")

# Находки, которые означают настоящую порчу и роняют exit-код.
BLOCKING_KINDS = frozenset({
    "null-байты",
    "не-utf8",
    "служебный-мусор",
    "синтаксис",
    "не компилируется",
    "нечитаемый",
})


class Finding(NamedTuple):
    """Одна находка по файлу."""

    path: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}: [{self.kind}] {self.detail}"


def _iter_sources(root: Path):
    root = Path(root)
    for name in SOURCE_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        for py in sorted(directory.glob("*.py")):
            yield py
    extra = root / "conftest.py"
    if extra.is_file():
        yield extra


def _find_junk_lines(text: str) -> List[int]:
    """Номера строк (с 1), где строка целиком состоит из служебного мусора."""
    return [
        idx
        for idx, line in enumerate(text.splitlines(), start=1)
        if JUNK_LINE_RE.match(line.strip())
    ]


def scan_file(path: Path) -> List[Finding]:
    """Проверить один Python-файл. Возвращает список находок (пусто — чисто)."""
    path = Path(path)
    findings: List[Finding] = []
    name = path.name

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [Finding(name, "нечитаемый", str(exc))]

    nuls = raw.count(b"\x00")
    if nuls:
        first = raw.find(b"\x00")
        findings.append(Finding(name, "null-байты", f"{nuls} шт., первый по смещению {first}"))

    # Файл должен быть валиден UTF-8; битый байт — тоже порча.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        findings.append(Finding(name, "не-utf8", str(exc)))
        return findings  # дальше разбирать нечего, текста нет

    for line_no in _find_junk_lines(text):
        findings.append(Finding(name, "служебный-мусор", f"строка {line_no} целиком — обрывок потока"))

    findings.extend(_check_structure(name, text))
    findings.extend(_check_completion(name, text))
    return findings


def _check_structure(name: str, text: str) -> List[Finding]:
    """Файл должен разбираться ast-ом (проверка без запуска)."""
    try:
        ast.parse(text)
    except SyntaxError as exc:
        return [Finding(name, "синтаксис", f"строка {exc.lineno}: {exc.msg}")]
    return []


def _check_completion(name: str, text: str) -> List[Finding]:
    """Признак обрыва записи: текст не заканчивается переводом строки."""
    if text and not text.endswith("\n"):
        stripped = text.rstrip()
        last = stripped.splitlines()[-1] if stripped else ""
        return [Finding(name, "обрыв", f"нет завершающего \\n, последняя строка: {last[-60:]!r}")]
    return []


def compile_check(root: Path) -> List[Finding]:
    """Реально скомпилировать каждый .py — ловит то, что не видит ast поштучно."""
    findings: List[Finding] = []
    for py in _iter_sources(Path(root)):
        try:
            source = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(Finding(py.name, "нечитаемый", str(exc)))
            continue
        try:
            compile(source, str(py), "exec")
        except (SyntaxError, ValueError) as exc:
            findings.append(Finding(py.name, "не компилируется", str(exc)))
    return findings


def scan_tree(root: Path) -> List[Finding]:
    """Полная проверка дерева проекта: содержимое + компиляция."""
    findings: List[Finding] = []
    for py in _iter_sources(Path(root)):
        findings.extend(scan_file(py))
    findings.extend(compile_check(Path(root)))
    return findings


def is_blocking(findings: List[Finding]) -> bool:
    """Есть ли среди находок настоящая порча (а не предупреждение)."""
    return any(f.kind in BLOCKING_KINDS for f in findings)


def summarize(findings: List[Finding]) -> Dict[str, int]:
    """Свести находки в счётчики по виду."""
    out: Dict[str, int] = {}
    for f in findings:
        out[f.kind] = out.get(f.kind, 0) + 1
    return out

# Строка добавлена патчем: инструмент записи срезает завершающий перевод
# строки, и без неё файл сам попадает под правило «обрыв».