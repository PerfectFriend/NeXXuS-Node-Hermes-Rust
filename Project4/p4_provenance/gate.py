"""Машиночитаемые факты для `tools/cycle_claim_gate.py` (пункт 13 плана).

Заявка Искателя: сверяющий гейт `cycle_claim_gate.py` детерминирован и ждёт
`facts.test_run.{passed,failed,collected}` и `facts.defect_registry.{open,closed,
total}`, но эти числа агенты набирали руками и переписывали в отчёт. Здесь числа
не набираются: они читаются из артефактов, которые уже произвели другие
инструменты.

* `test_run` — реальный прогон pytest с `--junit-xml`, разобранный как XML.
  Никакого разбора текста вывода, никаких «0 тестов» по умолчанию.
* `defect_registry` — файл `defect_registry.json` проекта.

Два свойства, ради которых модуль написан отдельно:

1. **Отсутствие данных не выдаётся за успех.** Если рабочий pytest не найден
   или отчёт не создан, возвращается `{"error": ...}`, а не нули. Гейт такую
   выдачу роняет — так и задумано.
2. **Гейт подключается живым импортом файла** `tools/cycle_claim_gate.py`
   (только чтение), а не его копии: расхождение копии с настоящим гейтом
   сделало бы проверку бессмысленной.

Рекурсии нет: `build_facts` запускает pytest по переданному каталогу, а тесты
этого модуля гоняют pytest по временному подпроекту из пары тестов, а не по
Project4.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import PROJECT_ROOT
from .paths import PROJECT_DIR, REPO_DIR, inside_root

#: Имя файла реестра дефектов в корне проекта.
REGISTRY_NAME = "defect_registry.json"

#: Статусы, которые считаются открытыми / закрытыми. Общий словарь проекта,
#: а не константы каждого модуля своими.
OPEN_STATUSES = ("open", "new", "wip", "todo", "reopened")
CLOSED_STATUSES = ("closed", "done", "fixed", "resolved")

GATE_REL = ("tools", "cycle_claim_gate.py")


# --------------------------------------------------------------------------
# поиск рабочего pytest
# --------------------------------------------------------------------------


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 900) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return 127, f"{cmd[0]}: не найден"
    except subprocess.TimeoutExpired:
        return 124, "таймаут"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def candidate_pytests(project: Path) -> List[List[str]]:
    """Кандидаты запуска pytest, от вероятных к отчаянным.

    На этой машине pytest стоит отдельным бинарником `~/build/bin/pytest` и НЕ
    импортируется интерпретатором по умолчанию, поэтому наивный
    `sys.executable -m pytest` даёт «No module named pytest» — и «0 тестов»
    молча превратились бы в ложно-зелёный отчёт.
    """
    cands: List[List[str]] = []
    for venv_py in (project / ".venv/bin/python", project / "venv/bin/python"):
        if venv_py.exists():
            cands.append([str(venv_py), "-m", "pytest"])
    which = shutil.which("pytest")
    if which:
        try:
            first = Path(which).read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
            if first and first[0].startswith("#!") and "python" in first[0]:
                interp = first[0][2:].strip().split()[0]
                if interp and Path(interp).exists():
                    cands.append([interp, "-m", "pytest"])
        except OSError:
            pass
        cands.append([which])
    for base in ("/home/thomas/build/bin/python3", sys.executable):
        if base and Path(base).exists():
            cands.append([base, "-m", "pytest"])
    return cands


def resolve_pytest(project: Path) -> Optional[List[str]]:
    """Первый кандидат, который реально отвечает на `--version`."""
    for cand in candidate_pytests(project):
        code, _ = _run(cand + ["--version"], None, timeout=60)
        if code == 0:
            return cand
    return None


# --------------------------------------------------------------------------
# разбор машинного отчёта
# --------------------------------------------------------------------------


def read_junit(path: os.PathLike | str) -> Dict[str, Any]:
    """Считать `test_run` из junit-xml. Единственный источник для pytest.

    Считаются узлы `testsuite`/`testsuites`, а не отдельные `<testcase>`:
    параметризация pytest иначе даёт двойной счёт.
    """
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"error": f"junit-xml не разобран: {exc}", "source": str(path)}
    # ВАЖНО: pytest пишет числа в узлах `testsuite`, а у корня `testsuites`
    # атрибутов нет. Чтение корня давало 0/0/0 — то есть «всё зелёное» из
    # прогона, который на самом деле падал. Поэтому суммируем все `testsuite`.
    nodes = list(root.iter("testsuite"))
    if not nodes:
        return {"error": "в junit-xml нет testsuite", "source": str(path)}
    collected = sum(_total(n) for n in nodes)
    failed = sum(_failed(n) for n in nodes)
    skipped = sum(_skipped(n) for n in nodes)
    return {"passed": max(collected - failed - skipped, 0), "failed": failed,
            "collected": collected, "skipped": skipped, "source": "pytest --junit-xml"}


def _int_attr(node: ET.Element, name: str) -> int:
    val = node.get(name)
    if val is None:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


def _failed(node: ET.Element) -> int:
    return _int_attr(node, "failures") + _int_attr(node, "errors")


def _skipped(node: ET.Element) -> int:
    return _int_attr(node, "skipped")


def _total(node: ET.Element) -> int:
    total = _int_attr(node, "tests")
    if total == 0:
        total = _int_attr(node, "failures") + _int_attr(node, "errors") + _int_attr(node, "skipped")
    return total


def _passed(node: ET.Element) -> int:
    return max(_total(node) - _failed(node) - _skipped(node), 0)


# --------------------------------------------------------------------------
# реальный прогон
# --------------------------------------------------------------------------


def run_tests(project: os.PathLike | str, target: Optional[str] = None,
              timeout: int = 900) -> Dict[str, Any]:
    """Реально прогнать pytest в каталоге проекта и вернуть факты прогона."""
    project = Path(project)
    if not project.is_dir():
        return {"error": f"каталог проекта не найден: {project}"}
    pytest = resolve_pytest(project)
    if pytest is None:
        return {"error": "рабочий pytest не найден — прогон НЕ выполнен; это не «0 тестов»",
                "runner": "pytest", "exit_code": None}
    handle, tmp_name = tempfile.mkstemp(suffix=".xml")
    os.close(handle)
    xml_path = Path(tmp_name)
    cmd = pytest + ["-q", "--junit-xml", str(xml_path)]
    if target:
        cmd.append(target)
    try:
        code, out = _run(cmd, str(project), timeout=timeout)
        if not xml_path.exists() or xml_path.stat().st_size == 0:
            facts: Dict[str, Any] = {
                "error": "junit-xml не создан — вероятен сбор ошибок на импорте "
                         "(SystemExit) или отсутствие тестов",
                "runner": "pytest", "exit_code": code,
            }
            if out:
                facts["stderr_tail"] = out.strip()[-600:]
            return facts
        facts = read_junit(xml_path)
        facts["runner"] = "pytest"
        facts["exit_code"] = code
        if "error" not in facts and code not in (0, 1) and facts.get("failed") == 0:
            facts["warning"] = f"pytest exit {code} при failed=0 — прогон подозрителен"
        return facts
    finally:
        xml_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# реестр дефектов
# --------------------------------------------------------------------------


def unknown_status_items(items: List[Any]) -> List[str]:
    """Записи, чей статус не входит в OPEN/CLOSED — тихая потеря дефекта.

    P4-D6: `read_registry` считал `total` по числу элементов, а `open`/`closed` —
    только по известным статусам, поэтому дефект без `status` давал
    `total=1 при open=closed=0`: счётчики молча разъезжаются с суммой статусов,
    и агент может заявить «дефектов не осталось», не потеряв ни одного числа.
    Такой реестр — ошибка данных, а не «ноль дефектов».
    """
    bad: List[str] = []
    for pos, item in enumerate(items):
        if not isinstance(item, dict):
            bad.append(f"запись #{pos + 1} не объект ({type(item).__name__})")
            continue
        status = str(item.get("status") or "").strip().lower()
        label = str(item.get("id") or f"запись #{pos + 1}")
        if not status:
            bad.append(f"{label}: нет status")
        elif status not in OPEN_STATUSES and status not in CLOSED_STATUSES:
            bad.append(f"{label}: неизвестный status «{status}»")
    return bad


def read_registry(project: os.PathLike | str = PROJECT_DIR,
                  name: str = REGISTRY_NAME) -> Optional[Dict[str, Any]]:
    """Прочитать реестр дефектов проекта. `None` — файла нет (гейт это увидит)."""
    path = Path(project) / name
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"error": f"реестр {name} не разобран: {exc}"}
    if isinstance(data, list):
        items: List[Any] = data
    elif isinstance(data, dict) and isinstance(data.get("defects"), list):
        items = data["defects"]
    elif isinstance(data, dict):
        out = {k: data[k] for k in ("open", "closed", "total") if k in data}
        out.setdefault("open", 0)
        out.setdefault("closed", out.get("total", 0) - out.get("open", 0))
        out.setdefault("total", out.get("closed", 0) + out.get("open", 0))
        out["source"] = name
        return out
    else:
        return {"error": f"реестр {name}: неожиданная структура"}
    unknown = unknown_status_items(items)
    if unknown:
        return {"error": f"реестр {name}: неизвестные статусы дефектов — "
                          f"счётчики open/closed не сойдутся с total: "
                          + "; ".join(unknown)}
    return {
        "open": sum(1 for d in items if isinstance(d, dict)
                    and str(d.get("status", "")).lower() in OPEN_STATUSES),
        "closed": sum(1 for d in items if isinstance(d, dict)
                      and str(d.get("status", "")).lower() in CLOSED_STATUSES),
        "total": len(items),
        "source": name,
    }


def registry_by_status(project: os.PathLike | str = PROJECT_DIR,
                       name: str = REGISTRY_NAME) -> Dict[str, int]:
    """Счётчики статусов из реестра — для проверки согласованности сумм."""
    path = Path(project) / name
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["defects"] if isinstance(data, dict) else data
    counts: Dict[str, int] = {}
    for item in items:
        if isinstance(item, dict):
            status = str(item.get("status", "")).lower() or "неизвестен"
            counts[status] = counts.get(status, 0) + 1
    return counts


# --------------------------------------------------------------------------
# сборка facts и проверка заявления
# --------------------------------------------------------------------------


def build_facts(project: os.PathLike | str = PROJECT_DIR,
                junit: Optional[os.PathLike | str] = None,
                target: Optional[str] = None,
                run: bool = True) -> Dict[str, Any]:
    """Собрать `facts` для гейта: `{"test_run": …, "defect_registry": …}`."""
    project = Path(project)
    if junit is not None:
        test_run: Dict[str, Any] = read_junit(junit)
        test_run.setdefault("runner", "pytest")
    elif run:
        test_run = run_tests(project, target=target)
    else:
        test_run = {"error": "прогон запрошен как отсутствующий (--no-run): "
                             "заявление о зелёных тестах нечем подтвердить"}
    return {"test_run": test_run, "defect_registry": read_registry(project)}


def load_gate(repo: os.PathLike | str = REPO_DIR):
    """Живой импорт настоящего `tools/cycle_claim_gate.py` (только чтение).

    Копия гейта внутри проекта означала бы, что проверяется не тот код, который
    запускает протокол.
    """
    path = Path(repo).resolve().joinpath(*GATE_REL)
    if not path.exists():
        raise FileNotFoundError(f"гейт не найден: {path}")
    spec = importlib.util.spec_from_file_location("livingcode_cycle_claim_gate", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"гейт не импортируется: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def claim_from_facts(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Эталонное заявление, построенное ИЗ фактов.

    Честное по построению: каждое число взято из того же места, откуда его
    потом сверяет гейт, поэтому расхождение с ним невозможно по определению.
    Нужно не для красоты, а как база сравнения — агент заполняет свои числа
    сам, и разница с этой базой и есть его завышение.

    `cycle_closed` по умолчанию `False`: закрыть цикл может только человек,
    факты о тестах этого не доказывают.
    """
    run = facts.get("test_run")
    reg = facts.get("defect_registry")
    run_ok = isinstance(run, dict) and not run.get("error")
    reg_ok = isinstance(reg, dict) and not reg.get("error")
    return {
        "tests_total": run.get("collected") if run_ok else None,
        "tests_passed": run.get("passed") if run_ok else None,
        "defects_closed": reg.get("closed") if reg_ok else None,
        "cycle_closed": False,
    }


def fact_defects(facts: Dict[str, Any]) -> List[str]:
    """Дыры, которые гейт НЕ видит, — найдены живой пробой, а не чтением кода.

    `cycle_claim_gate.check()` отбрасывает секцию только когда она `None`.
    А этот модуль по контракту возвращает `{"error": …}` — то есть словарь с
    признаком провала. Проверено живым импортом гейта: кейс

        facts = {"test_run": {"error": "pytest не найден — прогон НЕ выполнен"},
                 "defect_registry": {"error": "реестр не разобран"}}
        claim = {"tests_passed": None, "defects_closed": None, "cycle_closed": True}

    даёт **ноль** расхождений: `None != None` ложно, а `registry.get("open")`
    отсутствует и не сравнивается. То есть гейт подтверждал закрытие цикла при
    прогоне, которого не было, — ровно тот ложно-зелёный факт, который этот
    модуль обязан не производить.

    Горячий `tools/cycle_claim_gate.py` править нельзя (чужой владелец, общий
    инструмент протокола), поэтому дыра закрывается здесь: моя обёртка
    обязана сама сказать «фактов нет», даже если гейт молчит.
    """
    problems: List[str] = []
    for section, label in (("test_run", "прогон тестов"),
                           ("defect_registry", "реестр дефектов")):
        value = facts.get(section)
        if value is None:
            problems.append(f"нет фактического {label} — заявление нечем подтвердить")
        elif isinstance(value, dict) and value.get("error"):
            problems.append(f"{label} не получен: {value['error']}")
    return problems


def claim_defects(facts: Dict[str, Any], claim: Dict[str, Any]) -> List[str]:
    """Заявление, в котором числа не названы, — тоже не подтверждение.

    Гейт сверяет `passed != claim.get("tests_passed")`; когда обе стороны `None`
    (факт не получен, агент не назвал число), равенство выполняется и расхождения
    не видно. Такое «молчаливое зелёное» отсекается здесь.
    """
    problems: List[str] = []
    for claim_key in ("tests_passed", "tests_total", "defects_closed"):
        if claim_key in claim and claim.get(claim_key) is None:
            problems.append(
                f"заявление не называет число «{claim_key}» — нечем подтвердить"
            )
    return problems


def gate_check(facts: Dict[str, Any], claim: Dict[str, Any],
               repo: os.PathLike | str = REPO_DIR) -> List[str]:
    """Сверяющее заявление с фактами. Пусто — подтверждено.

    Три источника расхождений: настоящий гейт, `fact_defects` и `claim_defects`.
    Первые двое не пересекаются: гейт молчит там, где они срабатывают.
    """
    problems = list(load_gate(repo).check(claim, facts))
    for extra in (fact_defects(facts), claim_defects(facts, claim)):
        for item in extra:
            if item not in problems:
                problems.append(item)
    return problems


def gate_exit(facts: Dict[str, Any], claim: Dict[str, Any],
              repo: os.PathLike | str = REPO_DIR) -> int:
    """Код возврата гейта для одного кейса: 0 — подтверждено, 2 — расхождение."""
    return 0 if not gate_check(facts, claim, repo) else 2


def claim_case(name: str, claim: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    """Кейс в формате, который понимает `cycle_claim_gate.py` как входной файл."""
    return {"name": name, "claim": claim, "facts": facts}


def write_case(path: os.PathLike | str, case: Dict[str, Any],
               root: os.PathLike | str = PROJECT_DIR) -> Path:
    """Записать кейс в JSON. Путь обязан лежать внутри Project4 (пункт 11)."""
    target = inside_root(str(path), root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def facts_digest(facts: Dict[str, Any]) -> str:
    """Короткая строка со сводкой фактов — для журнала и отчёта."""
    run = facts.get("test_run") or {}
    reg = facts.get("defect_registry") or {}
    if run.get("error"):
        run_part = f"ПРОГОН НЕ ВЫПОЛНЕН ({run['error']})"
    else:
        run_part = (f"passed={run.get('passed', '-')} failed={run.get('failed', '-')} "
                    f"collected={run.get('collected', '-')}")
    if reg is None:
        reg_part = "реестра дефектов нет"
    elif reg.get("error"):
        reg_part = f"реестр не разобран ({reg['error']})"
    else:
        reg_part = (f"open={reg.get('open', '-')} closed={reg.get('closed', '-')} "
                    f"total={reg.get('total', '-')}")
    return f"{run_part}; {reg_part}"


__all__ = [
    "REGISTRY_NAME", "OPEN_STATUSES", "CLOSED_STATUSES", "GATE_REL",
    "unknown_status_items",
    "candidate_pytests", "resolve_pytest", "read_junit", "run_tests",
    "read_registry", "registry_by_status", "build_facts", "load_gate",
    "fact_defects", "claim_defects", "gate_check", "gate_exit", "claim_case",
    "write_case", "facts_digest", "PROJECT_ROOT",
]