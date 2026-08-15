#!/usr/bin/env python3
# Wrapper for evolution_engine.py (elemental-life) that calculates cycle number automatically
# Cycle = minutes since epoch (2021-01-01) // 240 (4-hour cycles)

import subprocess
import sys
from datetime import datetime, timezone

EPOCH = datetime(2021, 1, 1, tzinfo=timezone.utc)

def calculate_cycle() -> int:
    now = datetime.now(timezone.utc)
    minutes_since_epoch = int((now - EPOCH).total_seconds() // 60)
    return minutes_since_epoch // 240  # 4-hour cycles

def main():
    cycle = calculate_cycle()
    print(f"[evolution_elemental_life_cron] Cycle: {cycle}", file=sys.stderr)

    args = sys.argv[1:]

    cmd = [sys.executable, "evolution_engine.py", "--project", "elemental-life", "--cycle-id", str(cycle)] + args
    result = subprocess.run(cmd, cwd="/home/thomas/LivingCode/scripts")
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()