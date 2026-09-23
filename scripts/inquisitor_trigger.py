# HOT
#!/usr/bin/env python3
"""
Inquisitor Trigger — Called when supervisor detects issue
Emits inquisitor.started event and launches inquisitor agent.
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
    parser.add_argument("--issue", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, default=0)
    args = parser.parse_args()
    
    event = {
        "type": "inquisitor.started",
        "issue": args.issue,
        "project": args.project,
        "cycle": args.cycle,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"inquisitor.started.{args.project}.{args.issue.replace(' ', '_')}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp_file.rename(event_file)
    
    print(f"Emitted inquisitor.started for {args.project}: {args.issue}")
    
    cmd = ["hermes", "run", "inquisitor", "--issue", args.issue, "--project", args.project]
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
    except FileNotFoundError:
        subprocess.Popen(["python", "scripts/inquisitor_entry.py", "--issue", args.issue, "--project", args.project], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()