# HOT
#!/usr/bin/env python3
"""
Producer Entry Point — Checks promotion readiness, triggers artist/musician
Called by producer_trigger.py, emits producer.done event
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

def emit_event(event_type, data):
    event = {
        "type": event_type,
        **data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    event_file = EVENTS_DIR / f"{event_type}.{data.get('project','')}.cycle_{data.get('cycle',0)}.json"
    temp = event_file.with_suffix(".tmp")
    temp.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp.rename(event_file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, required=True)
    args = parser.parse_args()
    
    print(f"[PRODUCER] Проверка {args.project} цикл {args.cycle}")
    
    # Run promotion check
    result = subprocess.run(
        [sys.executable, "scripts/promote_check.py"],
        cwd=str(ROOT),
        capture_output=True, text=True
    )
    
    promoted = "промоутил" in result.stdout.lower() or "promoted" in result.stdout.lower()
    
    # Check if assets needed
    project_path = ROOT / "Projects" / args.project
    needs_assets = False
    if project_path.exists():
        banner_files = list(project_path.glob("**/banner*")) + list(project_path.glob("**/assets/banner*"))
        if not banner_files:
            needs_assets = True
    
    if needs_assets:
        print(f"[PRODUCER] Ассеты нужны для {args.project}, триггер artist")
        emit_event("artist.trigger", {
            "project": args.project,
            "cycle": args.cycle,
            "assets_needed": ["banner", "icon"]
        })
        subprocess.Popen([sys.executable, "scripts/artist_trigger.py", "--project", args.project, "--cycle", str(args.cycle)], cwd=str(ROOT))
    
    emit_event("producer.done", {
        "project": args.project,
        "cycle": args.cycle,
        "promoted": promoted,
        "assets_triggered": needs_assets
    })
    
    print(f"[PRODUCER] Готово. Промоутил: {promoted}, Ассеты: {needs_assets}")

if __name__ == "__main__":
    main()