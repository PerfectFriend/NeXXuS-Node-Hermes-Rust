"""Машиночитаемые факты для `tools/cycle_claim_gate.py` (пункт 16 плана).

Заявка Искателя: сверяющий гейт `cycle_claim_gate.py` детерминирован и ждёт
`facts.test_run.{passed,failed,collected}` и `facts.defect_registry.{open,
closed,total}`, но эти числа агенты набирали руками и переписывали в отчёт.
Здесь числа не набираются — они читаются из артефактов, которые произвели
другие инструменты.

* `test_run` — реальный прогон pytest с `--junit-xml`, разобранный как XML.
* `defect_registry` — файл `defect_registry.json` проекта.

Свойства, ради которых модуль написан отдельно:

1. **Отсутствие данных не выдаётся за успех.** Если рабочий pytest не
   найден или отчёт не создан, возвращается `{"error": ...}`, а не нули.
   Ложно-зелёный отчёт опаснее отсутствия отчёта.
2. **Гейт подключается живым импортом файла** `tools/cycle_claim_gate.py`
   (только чтение), а не его копии: расхождение копии с настоящим гейтом
   сделало бы проверку бессмысленной.
3. **Рекурсии нет.** `build_facts` запускает pytest по переданному каталогу,
   а тесты этого модуля гоняют pytest по временному подпроекту из пары
   тестов, а не по Project3 — иначе тест гейта гонял бы сам себя.
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
from typing import Any, Dict, List, Optional

from .paths import project_root

#: Имя файла реестра дефектов в корне проекта.
REGISTRY_NAME = "defect_registry.json"

#: Статусы, которые считаются открытыми / закрытыми.
OPEN_STATUSES = ("open", "new", "wip", "todo", "reopened")
CLOSED_STATUSES = ("closed", "done", "fixed", "resolved")

GATE_REL = ("tools", "cycle_claim_gate.py")


def livingcode_root() -> Path:
    """Корень LivingCode (родитель каталога Project3)."""
    return project_root().parent


# --------------------------------------------------------------------------
# поиск рабочего pytest
# --------------------------------------------------------------------------


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 900) -> tuple:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout)
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
            first = Path(which).read_text(encoding="utf-8",
                                          errors="ignore").splitlines()[:1]
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
        total = (_int_attr(node, "failures") + _int_attr(node, "errors")
                 + _int_attr(node, "skipped"))
    return total


def read_junit(path) -> Dict[str, Any]:
    """Считать `test_run` из junit-xml. Единственный источник для pytest.

    Считаются узлы `testsuite`/`testsuites`, а не отдельные `<testcase>`:
    параметризация pytest иначе даёт двойной счёт. ВАЖНО: pytest пишет
    числа в узлах `testsuite`, а у корня `testsuites` атрибутов нет — чтение
    только корня давало 0/0/0, то есть «всё зелёное» из прогона, который
    на самом деле падал. Поэтому суммируем все `testsuite`.
    """
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"error": f"junit-xml не разобран: {exc}", "source": str(path)}
    nodes = list(root.iter("testsuite"))
    if not nodes:
        return {"error": "в junit-xml нет testsuite", "source": str(path)}
    collected = sum(_total(n) for n in nodes)
    failed = sum(_failed(n) for n in nodes)
    skipped = sum(_skipped(n) for n in nodes)
    return {"passed": max(collected - failed - skipped, 0), "failed": failed,
            "collected": collected, "skipped": skipped,
            "source": "pytest --junit-xml"}


# --------------------------------------------------------------------------
# реальный прогон
# --------------------------------------------------------------------------


def run_tests(project, target: Optional[str] = None,
              timeout: int = 900) -> Dict[str, Any]:
    """Реально прогнать pytest в каталоге проекта и вернуть факты прогона."""
    project = Path(project)
    if not project.is_dir():
        return {"error": f"каталог проекта не найден: {project}"}
    pytest = resolve_pytest(project)
    if pytest is None:
        return {"error": "рабочий pytest не найден — прогон НЕ выполнен; "
                         "это не «0 тестов»", "runner": "pytest",
                "exit_code": None}
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


def registry_path(project=None) -> Path:
    return Path(project or project_root()) / REGISTRY_NAME


def read_registry(project=None, name: str = REGISTRY_NAME) -> Optional[Dict[str, Any]]:
    """Прочитать реестр дефектов. `None` — файла нет (гейт это увидит)."""
    path = Path(project or project_root()) / name
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"error": f"реестр {name} не разобран: {exc}"}
    if isinstance(data, dict) and isinstance(data.get("defects"), list):
        items = data["defects"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        out = {k: data[k] for k in ("open", "closed", "total") if k in data}
        out.setdefault("open", 0)
        out.setdefault("closed", out.get("total", 0) - out.get("open", 0))
        out.setdefault("total", out.get("closed", 0) + out.get("open", 0))
        out["source"] = name
        return out
    else:
        return {"error": f"реестр {name}: неожиданная структура"}
    return {
        "open": sum(1 for d in items if isinstance(d, dict)
                    and str(d.get("status", "")).lower() in OPEN_STATUSES),
        "closed": sum(1 for d in items if isinstance(d, dict)
                      and str(d.get("status", "")).lower() in CLOSED_STATUSES),
        "total": len(items),
        "source": name,
    }


def registry_by_status(project=None, name: str = REGISTRY_NAME) -> Dict[str, int]:
    """Счётчики статусов из реестра — для проверки согласованности сумм."""
    path = Path(project or project_root()) / name
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["defects"] if isinstance(data, dict) else data
    counts: Dict[str, int] = {}
    for item in items:
        if isinstance(item, dict):
            status = str(item.get("status", "")).lower() or "неизвестен"
            counts[status] = counts.get(status, 0) + 1
    return counts


def registry_entries(project=None, name: str = REGISTRY_NAME) -> List[Dict[str, Any]]:
    """Список записей реестра как есть — для сверки с суммами статусов."""
    path = Path(project or project_root()) / name
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["defects"] if isinstance(data, dict) else data
    return [item for item in items if isinstance(item, dict)]


# --------------------------------------------------------------------------
# сборка facts и проверка заявления
# --------------------------------------------------------------------------


def build_facts(project=None, junit=None, target: Optional[str] = None,
                run: bool = True) -> Dict[str, Any]:
    """Собрать `facts` для гейта: `{"test_run": …, "defect_registry": …}`."""
    project = Path(project or project_root())
    if junit is not None:
        test_run: Dict[str, Any] = read_junit(junit)
        test_run.setdefault("runner", "pytest")
    elif run:
        test_run = run_tests(project, target=target)
    else:
        test_run = {"error": "прогон запрошен как отсутствующий (--no-run): "
                             "заявление о зелёных тестах нечем подтвердить"}
    return {"test_run": test_run, "defect_registry": read_registry(project)}


def load_gate(repo=None):
    """Живой импорт настоящего `tools/cycle_claim_gate.py` (только чтение).

    Копия гейта внутри проекта означала бы, что проверяется не тот код,
    который запускает протокол.
    """
    path = Path(repo or livingcode_root()).resolve().joinpath(*GATE_REL)
    if not path.exists():
        raise FileNotFoundError(f"гейт не найден: {path}")
    spec = importlib.util.spec_from_file_location("livingcode_cycle_claim_gate", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"гейт не импортируется: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fact_defects(facts: Dict[str, Any]) -> List[str]:
    """Дыры, которые гейт НЕ видит — граница установлена живым запуском.

    Точная граница, а не приближение (проверено запуском настоящего
    `tools/cycle_claim_gate.py` на кейс-файле, а не чтением его кода):

    * Секция с `{"error": …}` гейтом отбрасывается. Если заявление назвало
      число, гейт всё равно ловит расхождение (`0 != None`) — то есть
      «факта нет» само по себе не проходит.
    * Дыра возникает, когда **заявление молчит** (`None`) одновременно с
      недоступным фактом: сравнение `None == None` истинно, расхождения не
      видно, и гейт подтверждает закрытие цикла при прогоне, которого
      не было. Этот случай ловит `claim_defects`.
    * Отсутствующая секция (`None`) гейт тоже пропускает по той же причине.

    Горячий `tools/cycle_claim_gate.py` править нельзя (чужой владелец,
    общий инструмент протокола), поэтому обе дыры закрываются здесь.
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

    Гейт сверяет `passed != claim.get("tests_passed")`; когда обе стороны
    `None`, равенство выполняется и расхождения не видно. Такое «молчаливое
    зелёное» отсекается здесь.
    """
    problems: List[str] = []
    for claim_key in ("tests_passed", "tests_total", "defects_closed"):
        if claim_key in claim and claim.get(claim_key) is None:
            problems.append(
                f"заявление не называет число «{claim_key}» — нечем подтвердить"
            )
    return problems


def gate_check(facts: Dict[str, Any], claim: Dict[str, Any],
               repo=None) -> List[str]:
    """Сверяющее заявление с фактами. Пусто — подтверждено."""
    problems = list(load_gate(repo).check(claim, facts))
    for extra in (fact_defects(facts), claim_defects(facts, claim)):
        for item in extra:
            if item not in problems:
                problems.append(item)
    return problems


def gate_exit(facts: Dict[str, Any], claim: Dict[str, Any], repo=None) -> int:
    """Код возврата гейта: 0 — подтверждено, 2 — расхождение."""
    return 0 if not gate_check(facts, claim, repo) else 2


def claim_from_facts(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Эталонное заявление, построенное ИЗ фактов.

    Честное по построению: каждое число взято из того же места, откуда его
    потом сверяет гейт. Нужно как база сравнения — агент заполняет свои
    числа сам, и разница с этой базой и есть его завышение.

    `cycle_closed` по умолчанию `False`: закрыть цикл может только человек,
    факты о тестах этого не доказывают.
    """
    run = facts.get("test_run")
    reg = facts.get("defect_registry")
    run_ok = isinstance(run, dict) and not run.get("error")
    reg_ok = isinstance(reg, dict) and not reg.get("error")
    # Сужающие проверки вынесены в условие: Pyright не переносит `isinstance`
    # через отдельные булевы переменные, а на None здесь и упало бы.
    return {
        "tests_total": run.get("collected") if isinstance(run, dict) and run_ok else None,
        "tests_passed": run.get("passed") if isinstance(run, dict) and run_ok else None,
        "defects_closed": reg.get("closed") if isinstance(reg, dict) and reg_ok else None,
        "cycle_closed": False,
    }


def claim_case(name: str, claim: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    """Кейс в формате, который понимает `cycle_claim_gate.py`."""
    return {"name": name, "claim": claim, "facts": facts}


def facts_digest(facts: Dict[str, Any]) -> str:
    """Короткая строка со сводкой фактов — для журнала и отчёта."""
    run = facts.get("test_run") or {}
    reg = facts.get("defect_registry")  # БЕЗ `or {}`: это стирало None,
    # и тогда ветка «реестра дефектов нет» была недостижимой — дайджест
    # печатал «open=-» вместо «реестра нет». Отсутствие реестра и реестр
    # с пустыми счётчиками — разные вещи, и это ровно то различие, которое
    # этот модуль обязан не терять.
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
    "candidate_pytests", "resolve_pytest", "read_junit", "run_tests",
    "read_registry", "registry_by_status", "registry_entries", "registry_path",
    "build_facts", "load_gate", "fact_defects", "claim_defects", "gate_check",
    "gate_exit", "claim_from_facts", "claim_case", "facts_digest",
    "livingcode_root",
]