# HOT
#!/usr/bin/env python3
"""
Searcher Trigger — Called when cycle starts or searcher needed
Emits searcher.started event and launches searcher agent.
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
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--topic", default="latest_ai_tools")
    args = parser.parse_args()
    
    event = {
        "type": "searcher.started",
        "cycle": args.cycle,
        "topic": args.topic,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"searcher.started.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp_file.rename(event_file)
    
    print(f"Emitted searcher.started for cycle {args.cycle}, topic: {args.topic}")
    
    cmd = ["hermes", "run", "searcher", "--cycle", str(args.cycle), "--topic", args.topic]
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
    except FileNotFoundError:
        subprocess.Popen(["python", "scripts/searcher_entry.py", "--cycle", str(args.cycle), "--topic", args.topic], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()