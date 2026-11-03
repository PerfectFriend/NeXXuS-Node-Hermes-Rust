import re, sys
p = "/home/thomas/.hermes/cache/web/arxiv.org-4a041df84c.md"
lines = open(p, encoding="utf-8", errors="ignore").read().split("\n")
hits = [i for i, l in enumerate(lines) if "Hermes" in l]
print("total lines:", len(lines), "| Hermes lines:", len(hits), flush=True)
# print hits beyond line 300 (body sections, not front matter)
want = [i for i in hits if i > 300]
for i in want[:400]:
    ln = lines[i].replace("|", " ").replace("\\*", "*")
    ln = re.sub(r"\s+", " ", ln).strip()
    if len(ln) < 40 and "Hermes" not in ln:
        continue
    print(f"{i+1}: {ln[:520]}", flush=True)
