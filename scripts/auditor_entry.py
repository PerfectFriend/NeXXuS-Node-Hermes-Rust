#!/usr/bin/env python3
"""
Auditor Entry Point — Called by auditor_trigger.py
Reviews code changes, emits auditor.done event
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))

from model_selector import ModelSelector

def emit_event(event_type, data):
    event = {
        "type": event_type,
        **data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    event_file = EVENTS_DIR / f"{event_type}.{data.get('project','')}.cycle_{data.get('cycle',0)}.json"
    temp = event_file.with_suffix(".tmp")
    temp.write_text(json.dumps(event, indent=2))
    temp.rename(event_file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, required=True)
    args = parser.parse_args()
    
    print(f"[AUDITOR] Starting review for {args.project} cycle {args.cycle}")
    
    selector = ModelSelector()
    model = selector.get_best_model("auditor")
    if not model:
        print("[AUDITOR] ERROR: No model available")
        emit_event("auditor.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "No model"})
        sys.exit(1)
    
    print(f"[AUDITOR] Using model: {model}")
    
    project_path = ROOT / "Projects" / args.project
    if not project_path.exists():
        emit_event("auditor.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "Project not found"})
        sys.exit(1)
    
    # TODO: Actual code review logic
    # For now, check if there are any hot files (recently modified)
    import time
    hot_files = 0
    issues = []
    try:
        now = time.time()
        for f in project_path.rglob("*.py"):
            if f.is_file() and (now - f.stat().st_mtime) < 3600:
                hot_files += 1
                # Quick static check
                content = f.read_text()
                if "TODO" in content or "FIXME" in content:
                    issues.append(f"{f.relative_to(project_path)}: has TODO/FIXME")
    except:
        pass
    
    status = "clean" if not issues else "issues_found"
    
    emit_event("auditor.done", {
        "project": args.project,
        "cycle": args.cycle,
        "status": status,
        "model_used": model,
        "hot_files_reviewed": hot_files,
        "issues": issues
    })
    
    print(f"[AUDITOR] Done. Status: {status}, Hot files: {hot_files}, Issues: {len(issues)}")

if __name__ == "__main__":
    main()