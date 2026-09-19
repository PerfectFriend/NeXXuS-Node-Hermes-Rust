#!/usr/bin/env python3
# Remove spurious "# HOT"/"# COLD" marker lines from ANY .git control file under /home/thomas/LivingCode.
import os

ROOT = "/home/thomas/LivingCode"
gitdirs = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    if dirpath == ROOT or os.path.basename(dirpath) == ".git":
        pass
    # skip walking into .git internals of others via pruning handled below
    if ".git" in dirnames:
        gitdirs.append(os.path.join(dirpath, ".git"))
        dirnames.remove(".git")  # don't recurse into .git at this level
    dirnames[:] = [d for d in dirnames if d not in (".git", ".venv", "venv",
                                                     "node_modules", "__pycache__", "saved_frames", ".hermes")]

gitdirs = sorted(set(gitdirs))
print("Found .git dirs:", len(gitdirs))

fixed_total = []
for gd in gitdirs:
    targets = []
    for root, dirs, files in os.walk(gd):
        dirs[:] = [d for d in dirs if d not in ("hooks", "objects", "info")]
        for f in files:
            targets.append(os.path.join(root, f))
    targets.append(os.path.join(gd, "info", "exclude"))
    for p in targets:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            lines = content.split("\n", 1)
            first = lines[0].rstrip("\r")
            if first in ("# HOT", "# COLD"):
                bak = p + ".bak"
                if not os.path.exists(bak):
                    with open(bak, "w", encoding="utf-8") as fh:
                        fh.write(content)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(lines[1] if len(lines) > 1 else "")
                fixed_total.append(p.replace(ROOT, "~"))
        except Exception as e:
            print("ERR", p, e)

print("FIXED total:", len(fixed_total))
for p in fixed_total:
    print("  ", p)