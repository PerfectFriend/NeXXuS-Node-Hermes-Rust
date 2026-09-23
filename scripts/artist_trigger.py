# HOT
#!/usr/bin/env python3
"""
Artist Trigger — Called when producer triggers artist (assets needed)
Emits artist.started event and launches artist agent.
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
    parser.add_argument("--assets", nargs="+", default=["banner", "icon"])
    args = parser.parse_args()
    
    event = {
        "type": "artist.started",
        "project": args.project,
        "cycle": args.cycle,
        "assets_needed": args.assets,
        "node": "totomoto",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    event_file = EVENTS_DIR / f"artist.started.{args.project}.cycle_{args.cycle}.json"
    temp_file = event_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(event, indent=2))
    temp_file.rename(event_file)
    
    print(f"Emitted artist.started for {args.project} (assets: {args.assets})")
    
    cmd = ["hermes", "run", "artist", "--project", args.project, "--cycle", str(args.cycle)]
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
    except FileNotFoundError:
        subprocess.Popen(["python", "scripts/artist_entry.py", "--project", args.project, "--cycle", str(args.cycle)], cwd=str(ROOT), start_new_session=True)

if __name__ == "__main__":
    main()