"""Диагностика пункта 13: почему кросс-файловая дедупликация расходится с тестами."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p1_memory import loader, validate
from p1_memory.crossfile import merged_view, plan_crossfile
from p1_memory.validate import dedupe_key, is_junk

ROOT = Path(__file__).resolve().parent.parent

pairs = [(p, loader.load(p)) for p in loader.iter_memory_files(ROOT / "memory")]
print("файлов:", len(pairs))

recs = []
for p, doc in pairs:
    for i in doc.get("insights") or []:
        if not is_junk(i):
            recs.append((p.name, i))
print("чистых записей:", len(recs))

nourl = [(f, i) for f, i in recs if not (i.get("source_url") or "").strip()]
print("без source_url:", len(nourl))
c_nourl = Counter(dedupe_key(i) for _, i in nourl)
print("ключей без url:", len(c_nourl), "повторов:", sum(1 for v in c_nourl.values() if v > 1))

c_all = Counter(dedupe_key(i) for _, i in recs)
print("уникальных пар всего:", len(c_all))

plan, stats = plan_crossfile(pairs)
print("stats:", stats)
print("элементов в плане:", len(plan))
for e in plan:
    print("   ", e["path"].name, e["stats"])

mv = merged_view(pairs)
keys = [dedupe_key(i) for i in mv]
print("merged_view:", len(mv), "уникальных ключей:", len(set(keys)))