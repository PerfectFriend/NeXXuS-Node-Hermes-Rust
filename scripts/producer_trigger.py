# HOT
#!/usr/bin/env python3
"""
Producer Trigger — Called when auditor.done event fires
Emits producer.trigger event and runs promotion check.
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
    
    # Emit producer.trigger event
    event = {
        "type": "producer.trigger",
        "project": args.project,
        "cycle": args.cycle,
        "action": "promote_check",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"producer.trigger.{args.project}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted producer.trigger for {args.project}")
    
    # Run promotion check immediately
    subprocess.run(["python", "scripts/promote_check.py"], cwd=str(ROOT))
    
    # Also trigger artist if project not yet promoted (assets needed)
    # This will be handled by producer agent logic

if __name__ == "__main__":
    main()