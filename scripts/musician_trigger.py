#!/usr/bin/env python3
"""
Musician Trigger — Called when artist.done event fires
Emits musician.started event and launches musician agent.
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
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--track-type", default="ambient", choices=["ambient", "battle", "menu", "victory"])
    args = parser.parse_args()
    
    event = {
        "type": "musician.started",
        "project": args.project,
        "cycle": args.cycle,
        "track_type": args.track_type,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"musician.started.{args.project}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted musician.started for {args.project} ({args.track_type})")
    
    cmd = ["hermes", "run", "musician", "--project", args.project, "--cycle", str(args.cycle)]
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
    except FileNotFoundError:
        subprocess.Popen(["python", "scripts/musician_entry.py", "--project", args.project, "--cycle", str(args.cycle)], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()