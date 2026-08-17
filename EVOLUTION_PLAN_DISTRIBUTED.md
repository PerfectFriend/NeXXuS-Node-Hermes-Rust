# Living Code Evolution Plan — Distributed, Trigger-Based, Offline-Capable

**Version:** 2.0  
**Date:** 2026-08-17  
**Status:** DESIGN PHASE — awaiting implementation approval

---

## 1. ARCHITECTURAL SHIFT: Cron → Event-Driven Pipeline

### Current Problem
- Cron jobs run on fixed schedule regardless of work availability
- Agents idle waiting for their cron slot
- No backpressure — producer pushes regardless of consumer readiness
- Hard to add/remove nodes dynamically

### Target: Trigger-Based Flow
```
┌─────────────┐    done    ┌─────────────┐    done    ┌─────────────┐
│   SEARCHER  │ ─────────► │    CODER    │ ─────────► │  AUDITOR    │
│  (finds     │  trigger   │  (implements│  trigger   │  (reviews   │
│   tasks)    │            │   code)     │            │   code)     │
└─────────────┘            └─────────────┘            └─────────────┘
       │                          │                          │
       ▼                          ▼                          ▼
  writes to              writes to                   writes to
  queue.json             queue.json                  queue.json
  + emits                + emits                     + emits
  EVENT                  EVENT                       EVENT
```

### Implementation: Lightweight Event Bus
**Option A: File-based (zero deps, works offline)**
```
~/.livingcode/events/
├── searcher.done.cycle_42.json
├── coder.superguard.done.cycle_42.json
├── auditor.superguard.done.cycle_42.json
└── producer.trigger.promote.json
```
Each agent: `watchdog` polls `events/` every 10s, processes new `.json` files, deletes after handling.

**Option B: Redis Streams (if Redis available)**
- `XADD livingcode:events * type=coder.done project=superguard cycle=42`
- Consumers: `XREAD BLOCK 5000 STREAMS livingcode:events $`
- Works over Tailscale mesh

**Option C: NATS (lightweight, built-in clustering)**
- `nats pub livingcode.coder.done '{"project":"superguard","cycle":42}'`
- Subscribers: `nats sub livingcode.*.done`
- Auto-discovers nodes on mesh

**Decision: Start with Option A (file-based), upgrade to Option B/C when needed.**

---

## 2. LOCAL LLM INFRASTRUCTURE (Offline-First)

### 2.1 Model Registry per Node
Each node maintains `/home/thomas/LivingCode/model_registry.local.json`:
```json
{
  "node_id": "totomoto",
  "models": [
    {"name": "qwen3:8b", "backend": "ollama", "size_gb": 4.7, "capabilities": ["code", "reasoning", "ru", "en"]},
    {"name": "deepseek-coder:6.7b", "backend": "ollama", "size_gb": 3.8, "capabilities": ["code", "python", "go"]},
    {"name": "nemotron-3.5-lightning", "backend": "ollama", "size_gb": 22, "capabilities": ["reasoning", "long_context"]},
    {"name": "qwen3-8b-64k", "backend": "ollama", "size_gb": 8.2, "capabilities": ["long_context", "ru", "en"]},
    {"name": "qwen2.5-coder:7b", "backend": "llama.cpp", "size_gb": 4.2, "capabilities": ["code", "fast"]},
    {"name": "whisper-large-v3", "backend": "whisper.cpp", "size_gb": 2.9, "capabilities": ["stt", "multilingual"]},
    {"name": "xtts-v2", "backend": "coqui", "size_gb": 1.8, "capabilities": ["tts", "voice_clone", "ru", "en"]}
  ],
  "gpu": "RTX 3060 12GB",
  "ram_gb": 32,
  "disk_free_gb": 450
}
```

### 2.2 Model Fallback Chains
```yaml
# /home/thomas/LivingCode/fallback_chains.yaml
chains:
  coder:
    - "deepseek-coder:6.7b"      # Primary: fast, good at code
    - "qwen2.5-coder:7b"         # Fallback 1: llama.cpp, no GPU needed
    - "qwen3:8b"                 # Fallback 2: general purpose
    - "nemotron-3.5-lightning"   # Fallback 3: heavy reasoning
  
  auditor:
    - "qwen3:8b"                 # Primary: good reasoning
    - "nemotron-3.5-lightning"   # Fallback: deep analysis
    - "deepseek-coder:6.7b"      # Fallback: code-focused
  
  searcher:
    - "qwen3-8b-64k"             # Primary: long context for research
    - "qwen3:8b"                 # Fallback
  
  professor:
    - "nemotron-3.5-lightning"   # Primary: best reasoning
    - "qwen3-8b-64k"             # Fallback: long context
  
  artist:
    - "qwen3:8b"                 # Prompt engineering for ComfyUI
    - "qwen3-8b-64k"             # Complex prompts
  
  musician:
    - "qwen3:8b"                 # Lyrics, structure
    - "xtts-v2"                  # TTS for vocal reference
  
  tts:
    - "xtts-v2"                  # Primary: voice cloning
    - "piper"                    # Fallback: fast, many voices
  
  stt:
    - "whisper-large-v3"         # Primary: best accuracy
    - "whisper-medium"           # Fallback: faster
```

### 2.3 Offline Model Sync
```bash
# Script: sync_models.sh — runs on each node
# Pulls missing models from central model store (or peer nodes via Tailscale)
rsync -avz --progress tailscale://unsloth-studio:/models/ /home/thomas/.ollama/models/
# Or via git-lfs in model registry repo
```

---

## 3. DISTRIBUTED COMPUTE MESH (Tailscale)

### 3.1 Node Capabilities Registry
Each node publishes `/home/thomas/LivingCode/nodes/<node_id>.json` to shared Vault:
```json
{
  "node_id": "unsloth-studio",
  "hostname": "unsloth-studio",
  "tailscale_ip": "100.x.y.z",
  "services": {
    "ollama": "http://100.x.y.z:11434",
    "vllm": "http://100.x.y.z:8000",
    "comfyui": "http://100.x.y.z:8188",
    "audio_stack": {
      "xtts": "http://100.x.y.z:5002",
      "whisper": "http://100.x.y.z:5003",
      "musicgen": "http://100.x.y.z:5004"
    }
  },
  "capabilities": ["heavy_llm", "training", "audio_tts", "audio_stt", "music_gen", "image_gen"],
  "gpu": "RTX 4090 24GB",
  "ram_gb": 64,
  "max_concurrent_jobs": 4,
  "current_load": 1,
  "status": "online",
  "last_heartbeat": "2026-08-17T10:30:00Z"
}
```

### 3.2 Task Router (runs on orchestrator node)
```python
# /home/thomas/LivingCode/scripts/task_router.py
class TaskRouter:
    def route(self, task_type: str, payload: dict) -> str:
        """Returns node_id to execute task on."""
        nodes = self.discover_nodes()
        candidates = [n for n in nodes if task_type in n["capabilities"] and n["current_load"] < n["max_concurrent_jobs"]]
        if not candidates:
            return "local"  # fallback
        # Prefer node with lowest load, then highest GPU
        return min(candidates, key=lambda n: (n["current_load"], -n.get("gpu_score", 0)))["node_id"]
    
    def dispatch(self, node_id: str, task: dict) -> str:
        """Send task to node via HTTP or SSH."""
        if node_id == "local":
            return self.run_local(task)
        node = self.get_node(node_id)
        # POST to node's task endpoint
        resp = requests.post(f"{node['services']['task_api']}/execute", json=task, timeout=300)
        return resp.json()["job_id"]
```

### 3.3 Audio Stack Offloading (Concrete Example)
```
Coder (on totomoto) needs TTS for DJ Musician task
    │
    ├─ Checks local: xtts-v2 available? YES → run local
    │
    └─ If NO or GPU busy:
        │
        ├─ Query nodes.json → unsloth-studio has audio_stack.xtts
        │
        ├─ POST to http://100.x.y.z:5002/tts
        │   { "text": "...", "voice": "speaker_1.wav", "language": "ru" }
        │
        └─ Receives audio file, saves to Vault
```

### 3.4 Vault Synchronization
```bash
# /home/thomas/LivingCode/scripts/vault_sync.sh
# Runs every 5 min via cron OR on file change (inotify)

VAULT_LOCAL="/home/thomas/Documents/ObsidianVault"
VAULT_REMOTE="tailscale://unsloth-studio:/home/thomas/Documents/ObsidianVault"
VAULT_REMOTE2="tailscale://dell:/home/thomas/Documents/ObsidianVault"

# Bidirectional sync with conflict resolution (git-based)
cd "$VAULT_LOCAL"
git add -A
git commit -m "Auto-sync $(date -u +%Y%m%d_%H%M%S)" || true

# Push to each remote
for remote in unsloth-studio dell; do
    git push "$remote" main --force-with-lease 2>/dev/null || echo "Push to $remote failed"
    git pull "$remote" main --rebase 2>/dev/null || echo "Pull from $remote failed"
done

# Also sync LivingCode artifacts
rsync -avz --delete /home/thomas/LivingCode/artifacts/ "tailscale://unsloth-studio:/home/thomas/LivingCode/artifacts/"
rsync -avz --delete /home/thomas/LivingCode/CompleteProjects/ "tailscale://unsloth-studio:/home/thomas/LivingCode/CompleteProjects/"
```

---

## 4. TRIGGER-BASED PIPELINE IMPLEMENTATION

### 4.1 Event Types
```json
{
  "event_types": {
    "cycle.start": { "cycle": 42, "timestamp": "..." },
    "searcher.done": { "cycle": 42, "findings": [...], "next": "coder" },
    "coder.started": { "cycle": 42, "project": "superguard", "node": "totomoto" },
    "coder.done": { "cycle": 42, "project": "superguard", "hot_files": 3, "next": "auditor" },
    "auditor.started": { "cycle": 42, "project": "superguard" },
    "auditor.done": { "cycle": 42, "project": "superguard", "status": "clean", "next": "producer" },
    "producer.trigger": { "cycle": 42, "action": "promote_check" },
    "promotion.done": { "project": "superguard", "new_project": "elemental-life-game-by-toto" },
    "artist.trigger": { "project": "superguard", "assets_needed": ["banner", "icon"] },
    "artist.done": { "project": "superguard", "assets": [...] },
    "musician.trigger": { "project": "superguard", "track_type": "ambient" },
    "musician.done": { "project": "superguard", "track_path": "..." },
    "professor.trigger": { "topic": "vllm_optimization", "priority": "high" },
    "professor.done": { "topic": "vllm_optimization", "knowledge_path": "..." },
    "inquisitor.trigger": { "issue": "build_failure", "project": "superguard" },
    "inquisitor.done": { "issue": "build_failure", "fix": "..." },
    "supervisor.check": { "cycle": 42, "metrics": {...} },
    "supervisor.correction": { "action": "pause_coder", "project": "elemental-life", "reason": "stuck" }
  }
}
```

### 4.2 Agent Watchdog (replaces cron)
```python
# /home/thomas/LivingCode/scripts/agent_watchdog.py
# Runs as daemon, ONE per node

import json, time, subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

EVENTS_DIR = Path("/home/thomas/LivingCode/events")
HANDLERS = {
    "searcher.done": "python scripts/coder_trigger.py --project {project}",
    "coder.done": "python scripts/auditor_trigger.py --project {project}",
    "auditor.done": "python scripts/producer_trigger.py --project {project}",
    "producer.trigger": "python scripts/promote_check.py",
    "artist.trigger": "python scripts/artist.py --project {project}",
    "musician.trigger": "python scripts/musician.py --project {project}",
    "professor.trigger": "python scripts/professor.py --topic {topic}",
    "inquisitor.trigger": "python scripts/inquisitor.py --issue {issue}",
    "supervisor.check": "python scripts/supervisor.py --check",
}

class EventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith(".json"):
            self.process(Path(event.src_path))
    
    def process(self, path):
        try:
            data = json.loads(path.read_text())
            event_type = data.get("type")
            if event_type in HANDLERS:
                cmd = HANDLERS[event_type].format(**data)
                print(f"[watchdog] Triggering: {cmd}")
                subprocess.Popen(cmd, shell=True)
            path.unlink()  # delete after processing
        except Exception as e:
            print(f"[watchdog] Error processing {path}: {e}")

def main():
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(EventHandler(), str(EVENTS_DIR), recursive=False)
    observer.start()
    print("[watchdog] Started, watching", EVENTS_DIR)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
```

### 4.3 Trigger Scripts (examples)
```python
# scripts/coder_trigger.py
# Called when searcher.done event fires
import argparse, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
args = parser.parse_args()

# Write coder.started event
event = {
    "type": "coder.started",
    "project": args.project,
    "cycle": 42,  # from context
    "node": "totomoto",
    "timestamp": datetime.now(timezone.utc).isoformat()
}
(Path("events") / f"coder.started.{args.project}.json").write_text(json.dumps(event))

# Launch coder agent (via cronjob or direct)
subprocess.Popen(["hermes", "run", "coder", "--project", args.project])
```

---

## 5. RESOURCE-AWARE SCHEDULING

### 5.1 Node Health Monitor
```python
# Runs every 30s on each node, publishes to nodes/<node_id>.json
def collect_metrics():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "gpu_percent": get_gpu_utilization(),  # nvidia-smi
        "gpu_mem_percent": get_gpu_memory(),
        "ollama_loaded": get_loaded_models(),
        "active_jobs": count_active_jobs(),
        "temperature": get_gpu_temp()
    }
```

### 5.2 Dynamic Load Balancing
- If `gpu_mem_percent > 85%` → reject new heavy LLM tasks, route to peer
- If `ram_percent > 90%` → pause non-critical jobs
- If node offline > 60s → redistribute its jobs

---

## 6. MIGRATION PATH (Phased)

### Phase 1: Event Infrastructure (Week 1)
- [ ] Create `events/` directory structure
- [ ] Implement `agent_watchdog.py` daemon
- [ ] Add event emission to existing agents (searcher, coder, auditor, producer)
- [ ] Test file-based triggers locally
- [ ] Keep cron jobs as backup during transition

### Phase 2: Local LLM Registry (Week 1-2)
- [ ] Create `model_registry.local.json` on each node
- [ ] Implement `fallback_chains.yaml`
- [ ] Modify agents to use local models with fallback
- [ ] Test offline mode (disconnect internet, verify all agents work)

### Phase 3: Distributed Compute (Week 2-3)
- [ ] Deploy `nodes/<node_id>.json` to Vault
- [ ] Implement `task_router.py` on orchestrator
- [ ] Add HTTP task endpoints on worker nodes (unsloth-studio, dell)
- [ ] Offload TTS/STT/MusicGen to audio stack node
- [ ] Test cross-node task dispatch

### Phase 4: Vault Sync (Week 3)
- [ ] Implement bidirectional git sync script
- [ ] Add inotify triggers for instant sync
- [ ] Sync artifacts/ and CompleteProjects/
- [ ] Conflict resolution strategy (last-write-wins + manual review)

### Phase 5: Advanced (Week 4+)
- [ ] Supervisor auto-scaling (spin up cloud GPU if mesh overloaded)
- [ ] Predictive model loading (pre-load next likely model)
- [ ] Cross-node evolution cycles (coder on node A, auditor on node B)
- [ ] Federated learning sync (model weights between nodes)

---

## 7. CONFIGURATION FILES TO CREATE

```
/home/thomas/LivingCode/
├── model_registry.local.json          # Per-node (gitignored)
├── fallback_chains.yaml               # Shared (in Vault)
├── nodes/
│   ├── totomoto.json                  # Published to Vault
│   ├── unsloth-studio.json
│   └── dell.json
├── events/                            # Runtime (gitignored)
│   ├── searcher.done.cycle_42.json
│   └── ...
├── scripts/
│   ├── agent_watchdog.py              # Daemon
│   ├── task_router.py
│   ├── vault_sync.sh
│   ├── sync_models.sh
│   ├── node_health.py
│   ├── coder_trigger.py
│   ├── auditor_trigger.py
│   ├── producer_trigger.py
│   ├── artist_trigger.py
│   ├── musician_trigger.py
│   ├── professor_trigger.py
│   ├── inquisitor_trigger.py
│   └── supervisor_trigger.py
└── systemd/
    └── livingcode-watchdog.service    # Auto-start daemon
```

---

## 8. BACKWARD COMPATIBILITY

- Cron jobs remain enabled but **guarded**: only run if no event triggered in last 30 min
- `cycle_start.py` still runs every 4h as "heartbeat" and promotion check
- Journal/comm cron (`*/10`) stays for heartbeat
- Gradual migration: one agent at a time

---

## 9. RISKS & MITIGATIONS

| Risk | Mitigation |
|------|------------|
| Event loss (file deleted before processed) | Write to temp, rename atomic; watchdog processes on startup |
| Node split-brain (two nodes think they're primary) | Single orchestrator (totomoto) via Tailscale IP; others are workers |
| Vault sync conflicts | Git merge + timestamp; manual resolution for .md conflicts |
| Model version drift | `sync_models.sh` checks checksums weekly |
| Tailscale partition | Local fallback chains; queue persists locally until mesh heals |

---

## 10. SUCCESS METRICS

- **Latency**: Searcher→Coder trigger < 5s (vs 4h cron wait)
- **GPU Utilization**: >70% average across mesh (vs ~20% cron)
- **Offline Survival**: 100% agents functional without internet
- **Task Distribution**: Audio tasks on audio node, heavy LLM on 4090 node
- **Vault Consistency**: <30s sync lag across nodes

---

**Approval needed to begin Phase 1 implementation.**