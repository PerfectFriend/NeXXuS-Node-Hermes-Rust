#!/usr/bin/env python3
"""Auditor's independent hot-code tests for Projects/superguard (cycle 12339-12341).

Run:  python3 reports/auditor-20260924-hot-superguard-tests.py
Lives OUTSIDE the project (auditor practice: no test files injected into a COLD/HOT project tree).
Checks the two hot-code fixes and hunts for the same defect class elsewhere in the core.
"""
import json
import logging
import os
import stat
import sys
import tempfile
import threading
from pathlib import Path

logging.disable(logging.CRITICAL)  # keep audit output readable

sys.path.insert(0, "/home/thomas/LivingCode/Projects/superguard")
from superguard_core import SuperguardEngine, Status  # noqa: E402

fails = []


def check(name, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {name}: {type(e).__name__}: {e}")
        fails.append(name)


def test_evolve_refuses_when_frozen():
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    e.evolve()
    e.freeze()
    try:
        e.evolve()
        raise AssertionError("evolve did NOT refuse on FROZEN")
    except RuntimeError as ex:
        assert "FROZEN" in str(ex)
    assert e.state.subcycle == 1 and e.state.status == Status.FROZEN
    assert e.verify() is True


def test_freeze_survives_reset():  # FINDING #1 — expected to FAIL on current HEAD
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    e.evolve()
    e.freeze()
    e.reset()
    e.evolve()  # a FROZEN engine must not come back to life through reset()
    assert e.state.status == Status.FROZEN, (
        "reset() silently unfroze the engine -> evolved to "
        f"{e.state.status.value} subcycle {e.state.subcycle}"
    )


def test_load_state_preserves_frozen_guard():
    d = tempfile.mkdtemp()
    p = Path(d) / "s.json"
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    e.evolve()
    e.freeze()
    e.save_state(p)
    loaded = SuperguardEngine.load_state(p)
    assert loaded.state.status == Status.FROZEN
    try:
        loaded.evolve()
        raise AssertionError("loaded FROZEN engine evolved")
    except RuntimeError:
        pass


def test_save_state_is_atomic():
    d = tempfile.mkdtemp()
    p = Path(d) / "s.json"
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    e.evolve()
    e.save_state(p)
    assert not list(Path(d).glob("*.tmp")), "tmp debris on success"
    good = p.read_bytes()
    e.to_dict = lambda: (_ for _ in ()).throw(TypeError("boom"))
    try:
        e.save_state(p)
    except TypeError:
        pass
    assert not list(Path(d).glob("*.tmp")), "tmp debris on failure"
    assert p.read_bytes() == good, "known-good state file damaged"
    assert SuperguardEngine.load_state(p).state.subcycle == 1


def test_concurrent_evolve_and_save():
    d = tempfile.mkdtemp()
    p = Path(d) / "s.json"
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    errs = []

    def worker():
        try:
            for _ in range(30):
                e.evolve()
                e.save_state(p)
        except Exception as ex:  # noqa: BLE001
            errs.append(ex)

    ts = [threading.Thread(target=worker) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errs, errs
    json.loads(p.read_text())
    assert not list(Path(d).glob("*.tmp")), "tmp debris after concurrency"


def test_save_state_preserves_file_mode():  # FINDING #2 — expected to FAIL on current HEAD
    d = tempfile.mkdtemp()
    p = Path(d) / "s.json"
    p.write_text("{}")
    os.chmod(p, 0o644)
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    e.save_state(p)
    mode = stat.S_IMODE(p.stat().st_mode)
    assert mode == 0o644, f"save_state rewrote mode 0644 -> {oct(mode)} (mkstemp 0600)"


def test_deepcopy_isolation():
    e = SuperguardEngine({"name": "t", "version": "1.0"})
    e.evolve()
    s = e.get_state()
    s.metrics["x"] = 1
    s.config["name"] = "hacked"
    s.evolution_history.append({})
    assert "x" not in e.state.metrics
    assert e.state.config["name"] == "t"
    assert len(e.state.evolution_history) == 1
    e.get_evolution_history().append({})
    e.get_config()["name"] = "hacked2"
    assert len(e.state.evolution_history) == 1 and e.state.config["name"] == "t"


def test_from_dict_rejects_foreign_class():
    try:
        SuperguardEngine.from_dict({"engine_class": "Other", "state": {}})
        raise AssertionError("no ValueError")
    except ValueError:
        pass


if __name__ == "__main__":
    print(f"superguard hot-code audit, python {sys.version.split()[0]}, HEAD file: superguard_core.py")
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            check(name, fn)
    print("\nFAILS:", fails if fails else "none")
    sys.exit(1 if fails else 0)
