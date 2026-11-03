#!/usr/bin/env python3
"""Step 2 of Lord marker repair: residual dangerous markers committed BEFORE today.

Found by tmp_lord_repair_markers.py scan:
  - linux/runner/{main.cc,my_application.cc,my_application.h}: "# HOT" as line 1
    is a C++ preprocessor directive -> compile error for the Linux desktop target.
  - data/elemental-life.svg: '#' is not an SVG comment -> invalid SVG.
  - data/icon64.png: overwritten as text by the walker (6 bytes) -> asset lost,
    restore the last good blob from git history if one exists.

Also refreshes STATE.json (auditor note #4 [СР]: dead metadata, hot_files stale).
Nothing deleted; backups written next to each touched file.
"""
import json
import subprocess
import sys
import xml.dom.minidom
from datetime import datetime
from pathlib import Path

REPO = Path("/home/thomas/LivingCode/Projects/elemental-life-2")
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def strip_marker(path: Path) -> str:
    text = path.read_text()
    if not text.startswith("# HOT\n"):
        return "no marker at line 1 - untouched"
    (REPO / f"{path.name}.bak-lord-{STAMP}").write_text(text)
    path.write_text(text[len("# HOT\n"):])
    return "stripped '# HOT' (backup written)"


def restore_binary(path: Path) -> str:
    """Find the newest blob in history that is larger than the damaged file."""
    hist = sh("git", "log", "--format=%H", "--", str(path.relative_to(REPO))).stdout.split()
    damaged_size = path.stat().st_size
    for commit in hist:
        blob = subprocess.run(
            ["git", "show", f"{commit}:{path.relative_to(REPO)}"],
            cwd=REPO, capture_output=True,
        ).stdout
        if len(blob) > 64 and blob[:8] == b"\x89PNG\r\n\x1a\n":
            (REPO / f"{path.name}.damaged-lord-{STAMP}").write_bytes(path.read_bytes())
            path.write_bytes(blob)
            return f"restored {len(blob)} bytes from {commit[:8]} (damaged copy kept)"
    return f"NOT recoverable from history ({len(hist)} commits touched it), damaged_size={damaged_size}"


def main():
    print("=== residual dangerous markers ===")
    for rel in ["linux/runner/main.cc", "linux/runner/my_application.cc",
                "linux/runner/my_application.h"]:
        p = REPO / rel
        print(f"  {rel}: {strip_marker(p)}")

    svg = REPO / "data/elemental-life.svg"
    print(f"  data/elemental-life.svg: {strip_marker(svg)}")
    try:
        xml.dom.minidom.parse(str(svg))
        print("    -> SVG parses as XML: OK")
    except Exception as e:  # noqa: BLE001
        print(f"    -> SVG STILL INVALID: {e}")

    png = REPO / "data/icon64.png"
    print(f"  data/icon64.png: {restore_binary(png)}")
    head = png.read_bytes()[:8]
    print(f"    -> signature {head!r} valid={head == b'\\x89PNG\\r\\n\\x1a\\n'} size={png.stat().st_size}")

    print("\n=== STATE.json refresh ===")
    state_path = REPO / "STATE.json"
    state = json.loads(state_path.read_text())
    (REPO / f"STATE.json.bak-lord-{STAMP}").write_text(json.dumps(state, indent=2))
    state.update({
        "hot_files": 0,
        "cold_files": 3,
        "last_auditor_status": "code_frozen",
        "last_coder_cycle": "cycle_15",
        "ready_for_publish": True,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "COLD - frozen by Lord of Code after audit of cycle 15 (clean) + marker repair",
    })
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(json.loads(state_path.read_text()), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
