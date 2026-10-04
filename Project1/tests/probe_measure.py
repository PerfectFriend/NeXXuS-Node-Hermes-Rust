"""Одноразовая проба: замер дефекта кросс-файловых дублей на реальных данных."""
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path("/home/thomas/LivingCode/Project1")
sys.path.insert(0, str(ROOT))

from p1_memory import loader, validate  # noqa: E402

start = int(Path("/tmp/coder_p1_start").read_text().strip())
print("прошло", int(time.time()) - start, "с из 2700")

pairs = [(p, loader.load(p)) for p in loader.iter_memory_files(ROOT)]
recs = [(p.name, i) for p, d in pairs for i in (d.get("insights") or []) if not validate.is_junk(i)]
print("файлов", len(pairs), "чистых записей", len(recs))

nourl = [(f, i) for f, i in recs if not (i.get("source_url") or "").strip()]
cn = Counter(validate.dedupe_key(i) for _, i in nourl)
print("без url:", len(nourl), "уникальных ключей:", len(cn),
      "ключей с дублями:", sum(1 for v in cn.values() if v > 1))

allk = Counter(validate.dedupe_key(i) for _, i in recs)
print("уникальных пар (topic,source_url):", len(allk))

# сколько дублей внутри одного файла сейчас
inside = 0
for p, d in pairs:
    items = [i for i in (d.get("insights") or []) if not validate.is_junk(i)]
    inside += len(items) - len({validate.dedupe_key(i) for i in items})
print("дублей внутри файлов:", inside)
