# HOT
#!/usr/bin/env python3
"""
Coder Trigger — Called when searcher.done event fires
Emits coder.started event and launches coder agent.
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
    
    # Emit coder.started event
    event = {
        "type": "coder.started",
        "project": args.project,
        "cycle": args.cycle,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"coder.started.{args.project}.cycle_{args.cycle}.json"
    # Atomic write
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted coder.started for {args.project}")
    
    # Launch coder via hermes (or direct if hermes not available)
    # Using cronjob trigger for now - in future will use task_router
    cmd = [
        "hermes", "run", "coder",
        "--project", args.project,
        "--cycle", str(args.cycle)
    ]
    
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
        print(f"Launched coder for {args.project}")
    except FileNotFoundError:
        # Fallback: direct python execution
        print("hermes not found, using direct execution")
        subprocess.Popen([
            "python", "scripts/coder_entry.py",
            "--project", args.project,
            "--cycle", str(args.cycle)
        ], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()