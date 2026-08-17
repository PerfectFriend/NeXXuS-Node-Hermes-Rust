#!/usr/bin/env python3
"""
Supervisor Trigger — Periodic health check and corrections
Called by cron every 15 min as backup, or by watchdog on event.
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
    parser.add_argument("--cycle", type=int, default=0)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    
    # Emit supervisor.check event
    event = {
        "type": "supervisor.check",
        "cycle": args.cycle,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"supervisor.check.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted supervisor.check for cycle {args.cycle}")
    
    if not args.check_only:
        cmd = ["hermes", "run", "supervisor", "--cycle", str(args.cycle)]
        try:
            subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
        except FileNotFoundError:
            subprocess.Popen(["python", "scripts/supervisor_entry.py", "--cycle", str(args.cycle)], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()