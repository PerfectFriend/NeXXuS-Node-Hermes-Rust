# HOT
#!/usr/bin/env python3
"""
Supervisor Correction — Applies corrective actions
Called when supervisor detects issues requiring intervention.
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
    parser.add_argument("--action", required=True, choices=["pause_coder", "resume_coder", "restart_agent", "requeue_project", "alert"])
    parser.add_argument("--project", required=True)
    parser.add_argument("--reason", default="")
    parser.add_argument("--cycle", type=int, default=0)
    args = parser.parse_args()
    
    event = {
        "type": "supervisor.correction",
        "action": args.action,
        "project": args.project,
        "reason": args.reason,
        "cycle": args.cycle,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"supervisor.correction.{args.action}.{args.project}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted supervisor.correction: {args.action} on {args.project} ({args.reason})")
    
    # Execute correction
    if args.action == "pause_coder":
        # Pause coder cron job
        subprocess.run(["cronjob", "pause", "LV-coder-" + args.project], capture_output=True)
    elif args.action == "resume_coder":
        subprocess.run(["cronjob", "resume", "LV-coder-" + args.project], capture_output=True)
    elif args.action == "restart_agent":
        # Kill and restart agent process
        subprocess.run(["pkill", "-f", f"coder.*{args.project}"], capture_output=True)
        subprocess.Popen(["hermes", "run", "coder", "--project", args.project], cwd=str(ROOT))
    elif args.action == "requeue_project":
        # Move project back to queue
        import promote
        promote.demote(args.project)
    elif args.action == "alert":
        # Send alert via hermes
        subprocess.run(["hermes", "send", "--to", "telegram", f"⚠️ Supervisor Alert: {args.reason}"], capture_output=True)

if __name__ == "__main__":
    main()