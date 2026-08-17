#!/usr/bin/env python3
"""
Professor Trigger — Called when searcher finds topic needing deep study
Emits professor.started event and launches professor agent.
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
    parser.add_argument("--topic", required=True)
    parser.add_argument("--priority", default="normal", choices=["low", "normal", "high", "urgent"])
    parser.add_argument("--cycle", type=int, default=0)
    args = parser.parse_args()
    
    event = {
        "type": "professor.started",
        "topic": args.topic,
        "priority": args.priority,
        "cycle": args.cycle,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"professor.started.{args.topic.replace(' ', '_')}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted professor.started for {args.topic} (priority: {args.priority})")
    
    cmd = ["hermes", "run", "professor", "--topic", args.topic, "--priority", args.priority]
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
    except FileNotFoundError:
        subprocess.Popen(["python", "scripts/professor_entry.py", "--topic", args.topic], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()