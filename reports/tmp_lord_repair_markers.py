#!/usr/bin/env python3
"""Lord-of-Code marker repair for elemental-life-2.

Facts (verified before running):
  - HEAD f11801b = audited clean state (cycle 15: 34/34 pytest, 22/22 flutter).
  - At 2026-09-28 01:20 a mtime-based walker stamped "# HOT" as line 1 into 20 files,
    including .dart/.kt/.java/.cc/.h/.xml/.svg/gradlew where '#' is NOT a comment
    or must not precede the XML declaration / shebang -> build break (flutter test
    died with "Error: Type 'HOT' not found").
  - The same walker removed "# HOT" from 4 .json files -> that edit actually RESTORES
    valid JSON, so it is kept.

Rule applied (minimal, reversible):
  - 20 non-json files  -> restore HEAD content (the audited state).
  - 4 json files       -> keep working-tree content, assert valid JSON.
  - nothing deleted, no source logic touched.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/thomas/LivingCode/Projects/elemental-life-2")


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def changed_files():
    out = sh("git", "diff", "--name-only").stdout.split()
    return out


def head_content(path):
    r = sh("git", "show", f"HEAD:{path}")
    if r.returncode != 0:
        raise RuntimeError(f"git show failed for {path}: {r.stderr.strip()}")
    return r.stdout


# extensions / names where a leading '#' is harmless or where the file must not be touched
SAFE_HASH = {".py", ".sh", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".properties",
             ".cmake", ".txt", ".md", ".gitignore", ".desktop", ".lock"}
SHEBANG_NAMES = {"gradlew", "gradlew.bat"}


def danger(path: Path, first_line: str):
    """Return a reason string if a leading '# HOT' breaks this file, else None."""
    if not first_line.strip() in ("# HOT", "# COLD", "// HOT", "// COLD"):
        return None
    name = path.name
    ext = path.suffix.lower()
    if first_line.startswith("//"):
        return None  # '//' is a valid comment in dart/kotlin/java/cc; fine
    if name in SHEBANG_NAMES:
        return "shebang destroyed (line 1 must start with '#!')"
    if ext == ".xml":
        return "XML declaration no longer first line -> invalid XML"
    if ext == ".svg":
        return "'#' is not an SVG comment -> invalid SVG"
    if ext in (".dart", ".kt", ".kts", ".java", ".cc", ".cpp", ".h", ".js", ".ts"):
        return "invalid comment syntax for this language -> compile error"
    if ext == ".png" or ext == ".jpg":
        return "binary asset overwritten as text"
    if ext == ".json":
        return "'#' is not valid JSON -> parse error"
    if ext in SAFE_HASH:
        return None
    return None


def main():
    changed = changed_files()
    restored, kept, failures = [], [], []

    for path in changed:
        p = REPO / path
        if path.endswith(".json"):
            try:
                json.loads(p.read_text())
                kept.append(path)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{path}: kept but JSON invalid: {e}")
            continue
        try:
            content = head_content(path)
        except RuntimeError as e:
            failures.append(str(e))
            continue
        p.write_text(content)
        restored.append(path)

    print(f"changed files at start: {len(changed)}")
    print(f"restored from HEAD  : {len(restored)}")
    for r in restored:
        print(f"    - {r}")
    print(f"kept (valid JSON)   : {len(kept)}")
    for k in kept:
        print(f"    - {k}")

    # residual scan: any tracked file still starting with a marker
    print("\n=== residual marker scan (all tracked files) ===")
    listed = sh("git", "ls-files").stdout.split()
    dangerous = []
    benign = 0
    for path in listed:
        p = REPO / path
        if not p.is_file():
            continue
        try:
            first = p.open("r", errors="replace").readline()
        except Exception:  # noqa: BLE001
            continue
        reason = danger(p, first)
        if reason:
            dangerous.append(f"{path} [{reason}]")
        elif first.strip() in ("# HOT", "# COLD", "// HOT", "// COLD"):
            benign += 1
    print(f"benign leading markers: {benign}")
    print(f"DANGEROUS leading markers: {len(dangerous)}")
    for d in dangerous:
        print(f"    ! {d}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"    !! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
