#!/usr/bin/env python3
"""
Task Router — Routes tasks to optimal node in Tailscale mesh
"""

import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
NODES_DIR = ROOT / "nodes"
VAULT = Path("/home/thomas/Documents/ObsidianVault")

class TaskRouter:
    def __init__(self):
        self.nodes = {}
        self.load_nodes()
    
    def load_nodes(self):
        """Load node capabilities from Vault and local."""
        # Local node
        local_file = NODES_DIR / "totomoto.json"
        if local_file.exists():
            self.nodes["totomoto"] = json.loads(local_file.read_text())
        
        # Remote nodes from Vault
        vault_nodes = VAULT / "LivingCode" / "nodes"
        if vault_nodes.exists():
            for f in vault_nodes.glob("*.json"):
                node_id = f.stem
                if node_id not in self.nodes:
                    self.nodes[node_id] = json.loads(f.read_text())
    
    def discover_nodes(self):
        """Return list of online nodes with capacity."""
        online = []
        for node_id, info in self.nodes.items():
            if info.get("status") == "online":
                # Check heartbeat freshness
                last = info.get("last_heartbeat")
                if last:
                    from dateutil import parser
                    age = (datetime.now(timezone.utc) - parser.isoparse(last)).total_seconds()
                    if age > 120:  # 2 min stale
                        continue
                online.append(info)
        return online
    
    def route(self, task_type: str, payload: dict = None) -> str:
        """Return node_id best suited for task_type."""
        candidates = [
            n for n in self.discover_nodes()
            if task_type in n.get("capabilities", [])
            and n.get("current_load", 0) < n.get("max_concurrent_jobs", 1)
        ]
        
        if not candidates:
            return "local"
        
        # Score: prefer lower load, then higher GPU tier
        def gpu_score(node):
            gpu = node.get("gpu", "").lower()
            if "4090" in gpu: return 100
            if "3090" in gpu: return 90
            if "3080" in gpu: return 80
            if "3060" in gpu: return 70
            if "2080" in gpu: return 60
            return 10
        
        best = min(candidates, key=lambda n: (n["current_load"], -gpu_score(n)))
        return best["node_id"]
    
    def dispatch(self, node_id: str, task: dict) -> dict:
        """Send task to node, return result."""
        if node_id == "local" or node_id == "totomoto":
            return self.run_local(task)
        
        node = self.nodes.get(node_id)
        if not node:
            return {"error": f"Node {node_id} not found"}
        
        # Try HTTP task API first
        task_api = node.get("services", {}).get("task_api")
        if task_api:
            try:
                resp = requests.post(
                    f"{task_api}/execute",
                    json=task,
                    timeout=300
                )
                return resp.json()
            except Exception as e:
                return {"error": f"HTTP dispatch failed: {e}"}
        
        # Fallback: SSH
        try:
            hostname = node.get("hostname", node_id)
            cmd = f"ssh {hostname} 'cd /home/thomas/LivingCode && python scripts/task_executor.py \'{json.dumps(task)}\''"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            return json.loads(result.stdout) if result.stdout else {"error": result.stderr}
        except Exception as e:
            return {"error": f"SSH dispatch failed: {e}"}
    
    def run_local(self, task: dict) -> dict:
        """Execute task locally via hermes or direct script."""
        task_type = task.get("type")
        
        # Map task types to scripts
        scripts = {
            "coder": "scripts/coder_entry.py",
            "auditor": "scripts/auditor_entry.py",
            "searcher": "scripts/searcher_entry.py",
            "producer": "scripts/producer_entry.py",
            "artist": "scripts/artist_entry.py",
            "musician": "scripts/musician_entry.py",
            "professor": "scripts/professor_entry.py",
            "inquisitor": "scripts/inquisitor_entry.py",
            "tts": "scripts/tts_entry.py",
            "stt": "scripts/stt_entry.py",
            "musicgen": "scripts/musicgen_entry.py",
        }
        
        script = scripts.get(task_type)
        if not script:
            return {"error": f"Unknown task type: {task_type}"}
        
        # Run via hermes for agent context
        cmd = f"hermes run {task_type} --project {task.get('project', '')} --payload '{json.dumps(task)}'"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, cwd=str(ROOT))
            return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "Task timed out"}
        except Exception as e:
            return {"error": str(e)}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-type", required=True)
    parser.add_argument("--payload", default="{}")
    parser.add_argument("--async", action="store_true", dest="async_mode")
    args = parser.parse_args()
    
    router = TaskRouter()
    payload = json.loads(args.payload)
    payload["type"] = args.task_type
    
    node = router.route(args.task_type, payload)
    print(f"Routing {args.task_type} to {node}")
    
    if args.async_mode:
        # Fire and forget
        import threading
        threading.Thread(target=lambda: router.dispatch(node, payload)).start()
        print("Dispatched async")
    else:
        result = router.dispatch(node, payload)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()