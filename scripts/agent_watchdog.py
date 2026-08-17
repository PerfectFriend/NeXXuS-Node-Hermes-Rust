#!/usr/bin/env python3
"""
Living Code Agent Watchdog — Event-driven daemon
Replaces cron-based scheduling with file-based event triggers.
Run as systemd service on each node.
"""

import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/thomas/LivingCode/logs/watchdog.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "logs").mkdir(parents=True, exist_ok=True)

# Event type -> handler command template
HANDLERS = {
    "searcher.done": "python {root}/scripts/coder_trigger.py --project {project} --cycle {cycle}",
    "coder.done": "python {root}/scripts/auditor_trigger.py --project {project} --cycle {cycle}",
    "auditor.done": "python {root}/scripts/producer_trigger.py --project {project} --cycle {cycle}",
    "producer.trigger": "python {root}/scripts/promote_check.py",
    "promotion.done": "python {root}/scripts/coder_trigger.py --project {new_project} --cycle {cycle}",
    "artist.trigger": "python {root}/scripts/artist_trigger.py --project {project} --cycle {cycle}",
    "artist.done": "python {root}/scripts/musician_trigger.py --project {project} --cycle {cycle}",
    "musician.done": "python {root}/scripts/producer_trigger.py --project {project} --cycle {cycle}",
    "professor.trigger": "python {root}/scripts/professor_trigger.py --topic {topic} --priority {priority}",
    "inquisitor.trigger": "python {root}/scripts/inquisitor_trigger.py --issue {issue} --project {project}",
    "supervisor.check": "python {root}/scripts/supervisor_trigger.py --cycle {cycle}",
    "supervisor.correction": "python {root}/scripts/supervisor_correction.py --action {action} --project {project} --reason {reason}",
    "node.health": "python {root}/scripts/node_health.py --node {node_id}",
}

class EventHandler(FileSystemEventHandler):
    def __init__(self):
        self.processing = set()
    
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".json" and path.name not in self.processing:
            self.processing.add(path.name)
            # Small delay to ensure file is fully written
            time.sleep(0.1)
            self.process_event(path)
            self.processing.discard(path.name)
    
    def on_moved(self, event):
        # Handle atomic rename (temp -> final)
        if event.dest_path.endswith(".json"):
            from watchdog.events import FileCreatedEvent
            fake_event = FileCreatedEvent(event.dest_path)
            self.on_created(fake_event)
    
    def process_event(self, path: Path):
        try:
            data = json.loads(path.read_text())
            event_type = data.get("type")
            
            if not event_type:
                log.warning(f"Event {path.name} has no 'type' field")
                path.unlink(missing_ok=True)
                return
            
            if event_type not in HANDLERS:
                # Started events are informational, not triggers
                if event_type.endswith(".started"):
                    log.debug(f"Ignoring informational event: {event_type}")
                    archive_dir = EVENTS_DIR / "archive" / datetime.now().strftime("%Y%m%d")
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    path.rename(archive_dir / path.name)
                    return
                log.warning(f"Unknown event type: {event_type} in {path.name}")
                path.unlink(missing_ok=True)
                return
            
            # Add metadata
            data.setdefault("root", str(ROOT))
            data.setdefault("received_at", datetime.now(timezone.utc).isoformat())
            data.setdefault("processed_by", "watchdog")
            
            # Format command
            cmd = HANDLERS[event_type].format(**data)
            log.info(f"Triggering: {event_type} -> {cmd}")
            
            # Execute in background
            subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Archive event instead of deleting (for debugging)
            archive_dir = EVENTS_DIR / "archive" / datetime.now().strftime("%Y%m%d")
            archive_dir.mkdir(parents=True, exist_ok=True)
            path.rename(archive_dir / path.name)
            
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in {path.name}: {e}")
            path.unlink(missing_ok=True)
        except Exception as e:
            log.error(f"Error processing {path.name}: {e}")

def process_existing_events():
    """Process any events that arrived while watchdog was down."""
    for path in sorted(EVENTS_DIR.glob("*.json")):
        log.info(f"Processing stale event: {path.name}")
        handler = EventHandler()
        handler.process_event(path)

def main():
    log.info("=" * 60)
    log.info("Starting Living Code Agent Watchdog")
    log.info(f"Watching: {EVENTS_DIR}")
    log.info("=" * 60)
    
    # Process any existing events first
    process_existing_events()
    
    # Start file watcher
    observer = Observer()
    observer.schedule(EventHandler(), str(EVENTS_DIR), recursive=False)
    observer.start()
    
    log.info("Watchdog running. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        observer.stop()
        observer.join()
        log.info("Watchdog stopped.")

if __name__ == "__main__":
    main()