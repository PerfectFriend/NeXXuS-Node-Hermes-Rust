# HOT
#!/usr/bin/env python3
"""
Node Health Monitor — Publishes metrics to nodes/<node_id>.json
Run every 30s via cron or systemd timer
"""

import json
import psutil
import subprocess
import requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
NODES_DIR = ROOT / "nodes"
NODE_ID = "totomoto"

def get_gpu_info():
    """Get GPU utilization and memory"""
    try:
        # Try nvidia-smi first
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "gpu_percent": int(parts[0]),
                "gpu_mem_used_mb": int(parts[1]),
                "gpu_mem_total_mb": int(parts[2]),
                "gpu_mem_percent": int(int(parts[1]) / int(parts[2]) * 100)
            }
    except:
        pass
    
    # Try rocm-smi for AMD
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            import json as json_lib
            data = json_lib.loads(result.stdout)
            # Parse AMD output
            return {"gpu_percent": data.get("gpu_use", 0)}
    except:
        pass
    
    return {"gpu_percent": 0, "gpu_mem_percent": 0}

def get_ollama_models():
    """Get loaded Ollama models"""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        models = []
        for line in result.stdout.strip().split('\n')[1:]:
            if line.strip():
                name = line.split()[0]
                models.append(name)
        return models
    except:
        return []

def get_lemonade_models():
    """Get loaded Lemonade models"""
    try:
        resp = requests.get("http://127.0.0.1:8000/v1/models", timeout=5)
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
    except:
        return []

def main():
    # Load existing node config
    node_file = Path(f"/home/thomas/LivingCode/nodes/{NODE_ID}.json")
    if node_file.exists():
        content = node_file.read_text()
        # Skip comment lines (starting with #)
        lines = [line for line in content.split('\n') if not line.strip().startswith('#')]
        clean_content = '\n'.join(lines)
        node = json.loads(clean_content)
    else:
        node = {"node_id": NODE_ID}
    
    # Update node info
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = get_gpu_info()
    
    node["cpu_percent"] = cpu
    node["ram_percent"] = ram.percent
    node["ram_used_gb"] = round(ram.used / (1024**3), 1)
    node["ram_total_gb"] = round(ram.total / (1024**3), 1)
    node["disk_percent"] = round(disk.used / disk.total * 100, 1)
    node["disk_free_gb"] = round(disk.free / (1024**3), 1)
    node["gpu_percent"] = gpu.get("gpu_percent", 0)
    node["gpu_mem_percent"] = gpu.get("gpu_mem_percent", 0)
    node["ollama_models"] = get_ollama_models()
    node["lemonade_models"] = get_lemonade_models()
    node["active_jobs"] = len(list(Path("/home/thomas/LivingCode/events").glob("*.json")))
    node["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    node["status"] = "online"
    
    # Save
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    node_file.write_text(json.dumps(node, indent=2))
    print(f"[{datetime.now().isoformat()}] Node health updated: CPU={cpu}%, RAM={ram.percent}%, GPU={gpu.get('gpu_percent', 0)}%")

if __name__ == "__main__":
    main()