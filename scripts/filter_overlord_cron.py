#!/usr/bin/env python3
# Wrapper for filter_overlord.py that calculates cycle number automatically
# Cycle = minutes since epoch (2021-01-01) // 10 (10-minute cycles)

import subprocess
import sys
from datetime import datetime, timezone

EPOCH = datetime(2021, 1, 1, tzinfo=timezone.utc)

def calculate_cycle() -> int:
    now = datetime.now(timezone.utc)
    minutes_since_epoch = int((now - EPOCH).total_seconds() // 60)
    return minutes_since_epoch // 10

def main():
    cycle = calculate_cycle()
    print(f"[filter_overlord_cron] Cycle: {cycle}", file=sys.stderr)
    
    # Pass through any additional arguments
    args = sys.argv[1:]
    
    # Run the main script with --cycle
    cmd = [sys.executable, "filter_overlord.py", "--scan-all", "--cycle", str(cycle)] + args
    result = subprocess.run(cmd, cwd="/home/thomas/LivingCode/scripts")
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()