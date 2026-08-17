#!/usr/bin/env python3
"""
Generate STATE.json for a project from evolution data.
Called by coders/auditor after each cycle.
"""
import json
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path("/home/thomas/LivingCode")
PROJECTS = ROOT / "Projects"

def count_hot_cold(project_path: Path):
    """Count hot (recently modified) vs cold files."""
    # Hot = modified in last 24h, Cold = older
    import time
    now = time.time()
    hot = 0
    cold = 0
    for f in project_path.rglob("*.py"):
        if f.is_file():
            mtime = f.stat().st_mtime
            if now - mtime < 86400:  # 24 hours
                hot += 1
            else:
                cold += 1
    return hot, cold

def get_plan_progress(project_path: Path):
    """Parse PLAN.md for total/done items."""
    plan_file = project_path / "PLAN.md"
    if not plan_file.exists():
        return 0, 0
    content = plan_file.read_text()
    # Count checkboxes: - [ ] and - [x]
    total = content.count("- [ ]") + content.count("- [x]")
    done = content.count("- [x]")
    return total, done

def get_latest_evolution_summary(project_path: Path):
    """Find latest evolution_summary_cycle_*.json"""
    summaries = list(project_path.glob("evolution_summary_cycle_*.json"))
    if not summaries:
        return None
    # Sort by cycle number
    def extract_cycle(p):
        import re
        m = re.search(r"cycle_(\d+)", p.name)
        return int(m.group(1)) if m else 0
    return max(summaries, key=extract_cycle)

def generate_state(project_name: str):
    project_path = PROJECTS / project_name
    if not project_path.exists():
        return None
    
    hot, cold = count_hot_cold(project_path)
    plan_total, plan_done = get_plan_progress(project_path)
    
    pct = int((plan_done / plan_total * 100)) if plan_total > 0 else 0
    
    summary = get_latest_evolution_summary(project_path)
    last_cycle = None
    if summary:
        import re
        m = re.search(r"cycle_(\d+)", summary.name)
        if m:
            last_cycle = f"cycle_{m.group(1)}"
    
    state = {
        "project": project_name,
        "plan_total": plan_total,
        "plan_done": plan_done,
        "completion_pct": pct,
        "hot_files": hot,
        "cold_files": cold,
        "last_coder_cycle": last_cycle,
        "last_auditor_status": None,  # TODO: auditor writes this
        "ready_for_publish": pct >= 100 and hot == 0,
        "updated_at": datetime.now().isoformat()
    }
    
    state_file = project_path / "STATE.json"
    state_file.write_text(json.dumps(state, indent=2))
    print(f"✅ Generated STATE.json for {project_name}: {pct}% complete, {hot} hot, {cold} cold")
    return state

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        generate_state(sys.argv[1])
    else:
        # Generate for all active projects
        queue_file = ROOT / "QUEUE.json"
        if queue_file.exists():
            q = json.loads(queue_file.read_text())
            for project in q.get("active", []):
                generate_state(project)