#!/usr/bin/env python3
"""
Coder Entry Point — Called by coder_trigger.py
Implements code changes, emits coder.done event
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
sys.path.insert(0, str(ROOT / "scripts"))

from model_selector import ModelSelector

def emit_event(event_type, data):
    """Emit event to events/ directory"""
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
    parser.add_argument("--task", default="implement")
    args = parser.parse_args()
    
    print(f"[CODER] Starting cycle {args.cycle} for {args.project}")
    
    # Select model
    selector = ModelSelector()
    model = selector.get_best_model("coder")
    if not model:
        print("[CODER] ERROR: No model available")
        emit_event("coder.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "No model", "hot_files": 0})
        sys.exit(1)
    
    print(f"[CODER] Using model: {model}")
    
    project_path = ROOT / "Projects" / args.project
    if not project_path.exists():
        print(f"[CODER] ERROR: Project not found at {project_path}")
        emit_event("coder.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "Project not found", "hot_files": 0})
        sys.exit(1)
    
    # Read PLAN.md to know what to do
    plan_file = project_path / "PLAN.md"
    plan = plan_file.read_text() if plan_file.exists() else ""
    
    # TODO: Actual coding logic here
    # For now, simulate work by running a simple check
    hot_files = 0
    try:
        # Count recently modified Python files
        import time
        now = time.time()
        for f in project_path.rglob("*.py"):
            if f.is_file() and (now - f.stat().st_mtime) < 3600:
                hot_files += 1
    except:
        pass
    
    # Simulate: if PLAN.md has unchecked items, do work
    if "- [ ]" in plan:
        print(f"[CODER] Plan has unchecked items, doing work...")
        # Here would be the actual LLM call to implement tasks
        # subprocess.run(["ollama", "run", model, f"Implement tasks from plan..."])
        status = "partial"
    else:
        print(f"[CODER] Plan complete or empty")
        status = "complete"
    
    # Emit done event
    emit_event("coder.done", {
        "project": args.project,
        "cycle": args.cycle,
        "status": status,
        "model_used": model,
        "hot_files": hot_files
    })
    
    print(f"[CODER] Done. Status: {status}, Hot files: {hot_files}")

if __name__ == "__main__":
    main()