# HOT
#!/usr/bin/env python3
"""
Supervisor Entry Point — Monitors protocol health, applies corrections
Called by supervisor_trigger.py, emits supervisor.correction events
"""

import argparse
import json
import subprocess
import sys
import time
import psutil
import shutil
import datetime
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

def emit_event(event_type, data):
    event = {
        "type": event_type,
        **data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    event_file = EVENTS_DIR / f"{event_type}.cycle_{data.get('cycle',0)}.json"
    temp = event_file.with_suffix(".tmp")
    temp.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp.rename(event_file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=0)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    
    print(f"[SUPERVISOR] Проверка здоровья протокола цикл {args.cycle}")
    
    corrections = []
    
    # Check 1: Event bus health
    events = list(EVENTS_DIR.glob("*.json"))
    if len(events) > 100:
        corrections.append({
            "action": "cleanup_events",
            "reason": f"Слишком много событий в очереди: {len(events)}",
            "severity": "warning"
        })
    
    # Check 2: Agent responsiveness (check recent events)
    now = time.time()
    stale_agents = []
    for agent in ["coder", "auditor", "searcher", "producer", "artist", "musician"]:
        recent = list(EVENTS_DIR.glob(f"{agent}.done*.json"))
        if recent:
            latest = max(recent, key=lambda f: f.stat().st_mtime)
            age = now - latest.stat().st_mtime
            if age > 3600:  # 1 hour
                stale_agents.append(f"{agent} (неактивен {age/60:.0f} мин)")
    
    if stale_agents:
        corrections.append({
            "action": "alert_stale_agents",
            "reason": f"Агенты неактивны: {', '.join(stale_agents)}",
            "severity": "warning"
        })
    
    # Check 3: Queue health
    import json
    queue_file = ROOT / "QUEUE.json"
    if queue_file.exists():
        queue = json.loads(queue_file.read_text())
        if len(queue.get("active", [])) == 0:
            corrections.append({
                "action": "alert_empty_active",
                "reason": "Нет активных проектов в очереди",
                "severity": "critical"
            })
        if len(queue.get("queue", [])) == 0:
            corrections.append({
                "action": "alert_empty_queue",
                "reason": "Очередь проектов пуста",
                "severity": "warning"
            })
    
    # Check 4: Disk space
    disk = shutil.disk_usage("/")
    if disk.free / disk.total < 0.1:
        corrections.append({
            "action": "alert_disk_space",
            "reason": f"Мало места на диске: {disk.free // (1024**3)} ГБ свободно",
            "severity": "critical"
        })
    
    # Check 5: RAM usage
    ram = psutil.virtual_memory()
    if ram.percent > 95:
        corrections.append({
            "action": "alert_ram",
            "reason": f"RAM заполнен на {ram.percent}%",
            "severity": "critical"
        })
    
    # Apply corrections
    for correction in corrections:
        action = correction["action"]
        reason = correction["reason"]
        severity = correction["severity"]
        
        print(f"[SUPERVISOR] {severity.upper()}: {reason}")
        
        if action == "cleanup_events":
            # Archive old events
            archive_dir = EVENTS_DIR / "archive" / datetime.now().strftime("%Y%m%d")
            archive_dir.mkdir(parents=True, exist_ok=True)
            for f in events[:-50]:  # Keep last 50
                f.rename(archive_dir / f.name)
        
        elif action == "alert_stale_agents":
            emit_event("supervisor.correction", {
                "action": "alert",
                "message": f"Агенты неактивны: {', '.join(stale_agents)}",
                "cycle": args.cycle
            })
        
        elif action == "alert_empty_active":
            emit_event("supervisor.correction", {
                "action": "alert",
                "message": "Нет активных проектов!",
                "cycle": args.cycle
            })
        
        elif action == "alert_empty_queue":
            emit_event("supervisor.correction", {
                "action": "alert",
                "message": "Очередь проектов пуста",
                "cycle": args.cycle
            })
        
        elif action == "alert_disk_space":
            emit_event("supervisor.correction", {
                "action": "alert",
                "message": "Критично мало места на диске",
                "cycle": args.cycle
            })
        
        elif action == "alert_ram":
            emit_event("supervisor.correction", {
                "action": "alert",
                "message": "Критично мало RAM",
                "cycle": args.cycle
            })
    
    if not corrections:
        print("[SUPERVISOR] Все проверки пройдены, проблем не обнаружено")
    
    emit_event("supervisor.check", {
        "cycle": args.cycle,
        "corrections_applied": len(corrections),
        "corrections": corrections,
        "status": "ok" if not corrections else "warnings"
    })
    
    print(f"[SUPERVISOR] Готово. Применено коррекций: {len(corrections)}")

if __name__ == "__main__":
    main()