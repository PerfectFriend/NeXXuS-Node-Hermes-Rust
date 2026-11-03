#!/usr/bin/env python3
"""Lord marker audit + repair for elemental-life-2 (2026-09-28).

Context (verified):
  - HEAD 20a1b0c = "snapshot before cycle 16-25". Uncommitted work by the coder
    (cycles 16-25, PLAN items 11-20) lives in the working tree; 3 of its tests fail.
  - The mtime-walker in orchestration/scripts/lord_of_code.py stamped "# HOT" as line 1
    into every non-md/json/log file at 09:20:58 -- including .xml/.svg/.csv/.lock/.dart/.kt/cc
    where '#' is NOT a comment (breaks AndroidManifest.xml, SVG, Dart compile).
  - Earlier Lord repair (reports/tmp_lord_repair_markers.py) restored ALL non-json files from
    HEAD, which would now destroy the coder's real work. This script is surgical instead:
    it strips the injected marker line ONLY when the rest of the file is byte-identical to HEAD
    (i.e. the file's sole change is the marker). Coder changes are never touched.

Modes:
  audit (default) - report classification, change nothing
  fix             - strip marker-only files back to HEAD content
"""
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/thomas/LivingCode/Projects/elemental-life-2")
MARKERS = ("# HOT", "# COLD")


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def head_bytes(path):
    r = sh("git", "show", f"HEAD:{path}")
    if r.returncode != 0:
        return None
    return r.stdout


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "audit"
    dirty = sh("git", "diff", "--name-only").stdout.split()
    print(f"dirty tracked files: {len(dirty)}")
    marker_only, mixed_marker, no_marker = [], [], []
    for path in dirty:
        p = REPO / path
        try:
            cur = p.read_text(errors="replace")
        except Exception as e:  # noqa: BLE001
            print(f"  unreadable {path}: {e}")
            continue
        lines = cur.splitlines(keepends=True)
        first = lines[0].strip() if lines else ""
        stripped = "".join(lines[1:]) if first in MARKERS else cur
        head = head_bytes(path)
        head_text = head if head is not None else None
        if first in MARKERS and head_text is not None and stripped == head_text:
            marker_only.append(path)
        elif first in MARKERS:
            mixed_marker.append(path)
        else:
            no_marker.append(path)

    print(f"\n=== A) marker-only (safe to strip -> returns to HEAD) : {len(marker_only)}")
    for p in marker_only:
        print(f"    {p}")
    print(f"\n=== B) marker + real changes (KEEP coder work, strip marker only) : {len(mixed_marker)}")
    for p in mixed_marker:
        print(f"    {p}")
    print(f"\n=== C) no marker / legitimately changed : {len(no_marker)}")
    for p in no_marker:
        print(f"    {p}")

    if mode != "fix":
        print("\naudit only -- nothing written")
        return 0

    fixed_a = fixed_b = 0
    for path in marker_only:
        (REPO / path).write_text(head_bytes(path))
        fixed_a += 1
    for path in mixed_marker:
        p = REPO / path
        cur = p.read_text(errors="replace")
        lines = cur.splitlines(keepends=True)
        p.write_text("".join(lines[1:]))
        fixed_b += 1
    print(f"\nfixed: {fixed_a} restored to HEAD, {fixed_b} marker-stripped (coder work kept)")

    # residual scan over ALL tracked files for language-invalid markers
    print("\n=== residual marker scan (tracked files) ===")
    BAD_EXT = {".xml", ".svg", ".dart", ".kt", ".kts", ".java", ".cc", ".cpp", ".h", ".js", ".ts",
               ".csv", ".lock", ".json", ".png", ".jpg", ".ico", ".webp"}
    dangerous = []
    for path in sh("git", "ls-files").stdout.split():
        p = REPO / path
        if not p.is_file():
            continue
        try:
            first = p.open("r", errors="replace").readline().strip()
        except Exception:  # noqa: BLE001
            continue
        if first in MARKERS and (p.suffix.lower() in BAD_EXT or p.name in ("gradlew", ".metadata")):
            dangerous.append(f"{path} (first line: {first!r})")
    print(f"DANGEROUS markers left: {len(dangerous)}")
    for d in dangerous:
        print(f"    ! {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
