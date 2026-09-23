# HOT
#!/usr/bin/env python3
"""
Promote completed project to CompleteProjects, pull next from queue.
Called by producer when STATE.json shows completion_pct >= 100 and hot_files == 0.
"""
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path("/home/thomas/LivingCode")
QUEUE_FILE = ROOT / "QUEUE.json"
PROJECTS = ROOT / "Projects"
COMPLETE = ROOT / "CompleteProjects"
QUEUE_DIR = ROOT / "QueueProjects"  # staging area for queued projects

def load_queue():
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"queue": [], "active": [], "completed": []}

def save_queue(q):
    QUEUE_FILE.write_text(json.dumps(q, indent=2))

def promote(project_name: str) -> bool:
    """Move completed project out, bring next from queue in."""
    q = load_queue()
    
    if project_name not in q["active"]:
        print(f"❌ Project {project_name} not in active list")
        return False
    
    src = PROJECTS / project_name
    if not src.exists():
        print(f"❌ Source project {src} does not exist")
        return False
    
    # 1. Move to CompleteProjects with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = COMPLETE / f"{project_name}_{timestamp}"
    shutil.move(str(src), str(dst))
    print(f"✅ Promoted {project_name} → {dst}")
    
    # 2. Remove from active, add to completed
    q["active"].remove(project_name)
    q["completed"].append({"name": project_name, "promoted_at": timestamp})
    
    # 3. Pull next from queue
    if q["queue"]:
        next_project = q["queue"].pop(0)
        name = next_project["name"]
        source = Path(next_project.get("source", ""))
        
        print(f"📥 Pulling {name} from queue (priority {next_project['priority']})")
        
        # Clone or copy from source
        target = PROJECTS / name
        if source.exists():
            shutil.copytree(source, target)
            print(f"   Copied from {source}")
        elif next_project.get("repo"):
            subprocess.run(["git", "clone", next_project["repo"], str(target)], check=True)
            print(f"   Cloned from {next_project['repo']}")
        else:
            print(f"   ⚠️ No source found for {name}, creating empty project")
            target.mkdir(parents=True, exist_ok=True)
        
        # Create STATE.json for new project
        state = {
            "plan_total": 0,
            "plan_done": 0,
            "completion_pct": 0,
            "hot_files": 0,
            "cold_files": 0,
            "last_coder_cycle": None,
            "last_auditor_status": None,
            "ready_for_publish": False,
            "initialized_at": datetime.now().isoformat()
        }
        (target / "STATE.json").write_text(json.dumps(state, indent=2))
        
        # Create empty PLAN.md
        (target / "PLAN.md").write_text("")
        
        q["active"].append(name)
        print(f"✅ {name} added to active projects")
    else:
        print("⚠️ Queue is empty, no next project to pull")
    
    save_queue(q)
    return True

def check_all_promotable():
    """Check all active projects for promotion readiness."""
    q = load_queue()
    promoted_any = False
    
    for project in q["active"][:]:  # copy list since we modify it
        state_file = PROJECTS / project / "STATE.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            if state.get("completion_pct", 0) >= 100 and state.get("hot_files", 0) == 0:
                print(f"🔥 {project} ready for promotion (100% complete, 0 hot files)")
                promote(project)
                promoted_any = True
        else:
            print(f"⚠️ {project} has no STATE.json, skipping promotion check")
    
    return promoted_any


def demote(project_name: str) -> bool:
    """Move project from active back to queue (front)."""
    q = load_queue()
    
    if project_name not in q["active"]:
        print(f"❌ Project {project_name} not in active list")
        return False
    
    src = PROJECTS / project_name
    if not src.exists():
        print(f"❌ Source project {src} does not exist")
        return False
    
    # Move back to QueueProjects staging
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    dst = QUEUE_DIR / project_name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    print(f"🔄 Demoted {project_name} → {dst}")
    
    # Remove from active, add to front of queue
    q["active"].remove(project_name)
    q["queue"].insert(0, {"name": project_name, "source": str(dst), "priority": 0, "demoted_at": datetime.now().isoformat()})
    
    save_queue(q)
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "demote":
            demote(sys.argv[2])
        else:
            promote(sys.argv[1])
    else:
        check_all_promotable()