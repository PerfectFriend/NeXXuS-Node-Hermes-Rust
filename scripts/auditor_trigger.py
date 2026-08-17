#!/usr/bin/env python3
"""
Auditor Trigger — Called when coder.done event fires
Emits auditor.started event and launches auditor agent.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import subprocess

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="superguard")
    parser.add_argument("--cycle", type=int, required=True)
    args = parser.parse_args()
    
    # Emit auditor.started event
    event = {
        "type": "auditor.started",
        "project": args.project,
        "cycle": args.cycle,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"auditor.started.{args.project}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted auditor.started for {args.project}")
    
    # Launch auditor
    cmd = [
        "hermes", "run", "auditor",
        "--project", args.project,
        "--cycle", str(args.cycle)
    ]
    
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
        print(f"Launched auditor for {args.project}")
    except FileNotFoundError:
        subprocess.Popen([
            "python", "scripts/auditor_entry.py",
            "--project", args.project,
            "--cycle", str(args.cycle)
        ], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()