#!/usr/bin/env python3
# Wrapper for banner_deploy_poller.py that auto-detects the current cycle

import subprocess
import sys
from pathlib import Path
import re

def find_latest_cycle():
    """Find the latest cycle number from filter reports"""
    artifacts_dir = Path("C:/LivingCode/artifacts")
    reports = list(artifacts_dir.glob("filter_report_cycle_*.json"))
    
    if not reports:
        print("No filter reports found", file=sys.stderr)
        return 1
    
    # Extract cycle numbers
    cycles = []
    for report in reports:
        match = re.search(r'filter_report_cycle_(\d+)\.json', report.name)
        if match:
            cycles.append(int(match.group(1)))
    
    if not cycles:
        print("No valid cycle numbers found", file=sys.stderr)
        return 1
    
    return max(cycles)

def main():
    cycle = find_latest_cycle()
    print(f"Auto-detected cycle: {cycle}")
    
    # Run the poller with --poll-once
    cmd = [
        sys.executable,
        "C:/LivingCode/scripts/banner_deploy_poller.py",
        f"--cycle={cycle}",
        "--poll-once"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd="/home/thomas/LivingCode/scripts")
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())