# HOT
#!/usr/bin/env python3
"""
Musician Entry Point — Night batch audio generation via unsloth-studio (Tailscale)
Runs 02:00-06:00, processes accumulated queue
Uses: unsloth-studio Lemonade API (ACE-Step, kokoro, Whisper)
"""

import argparse
import json
import sys
import time
import requests
import base64
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR = ROOT / "queue" / "musician"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# Unsloth-studio via Tailscale
UNSLOTH_API = os.environ.get("UNSLOTH_API", "http://100.x.y.z:8000/v1")  # Set via env

def emit_event(event_type, data):
    event = {
        "type": event_type,
        **data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    event_file = EVENTS_DIR / f"{event_type}.{data.get('project','')}.cycle_{data.get('cycle',0)}.json"
    temp = event_file.with_suffix(".tmp")
    temp.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp.rename(event_file)

def load_queue(project: str) -> list:
    queue_file = ROOT / "queue" / "musician" / f"{project}.json"
    if queue_file.exists():
        return json.loads(queue_file.read_text())
    return []

def save_queue(project: str, queue: list):
    queue_file = ROOT / "queue" / "musician" / f"{project}.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False))

def unsloth_musicgen(prompt: str, duration: int = 30) -> str:
    """Generate music via unsloth-studio ACE-Step-Music"""
    try:
        resp = requests.post(
            f"{UNSLOTH_API}/audio/generations",
            json={
                "model": "ACE-Step-Music",
                "prompt": prompt,
                "duration": duration
            },
            timeout=180
        )
        if resp.status_code == 200:
            audio_data = resp.content
            return base64.b64encode(audio_data).decode()
    except Exception as e:
        print(f"[MUSICIAN] ACE-Step error: {e}")
    return None

def unsloth_tts(text: str, voice: str = "kokoro-v1", language: str = "ru") -> str:
    """TTS via unsloth-studio kokoro-v1"""
    try:
        resp = requests.post(
            f"{UNSLOTH_API}/audio/speech",
            json={
                "model": "kokoro-v1",
                "input": text,
                "voice": voice,
                "response_format": "wav"
            },
            timeout=60
        )
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode()
    except Exception as e:
        print(f"[MUSICIAN] TTS error: {e}")
    return None

def unsloth_stt(audio_b64: str, language: str = "ru") -> str:
    """STT via unsloth-studio Whisper"""
    try:
        import tempfile
        audio_data = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(base64.b64decode(audio_b64))
            temp_path = f.name
        
        with open(temp_path, "rb") as f:
            files = {"file": (temp_path, open(temp_path, "rb"), "audio/wav")}
            data = {"model": "whisper-large-v3-turbo", "language": "ru"}
            resp = requests.post(
                f"{UNSLOTH_API}/audio/transcriptions",
                files=files,
                data=data,
                timeout=120
            )
        os.unlink(temp_path)
        
        if resp.status_code == 200:
            return resp.json().get("text", "")
    except Exception as e:
        print(f"[MUSICIAN] STT error: {e}")
    return None

def save_audio(project: str, track_type: str, audio_b64: str) -> str:
    project_path = ROOT / "Projects" / project
    music_dir = project_path / "assets" / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{track_type}_{timestamp}.wav"
    filepath = music_dir / filename
    
    audio_data = base64.b64decode(audio_b64)
    filepath.write_bytes(base64.b64decode(audio_b64))
    return str(filepath)

def load_queue(project: str) -> list:
    queue_file = ROOT / "queue" / "musician" / f"{project}.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    if queue_file.exists():
        return json.loads(queue_file.read_text())
    return []

def save_queue(project: str, queue: list):
    queue_file = ROOT / "queue" / "musician" / f"{project}.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--track-type", default="ambient", choices=["ambient", "battle", "menu", "victory", "tts", "stt"])
    parser.add_argument("--force", action="store_true", help="Run even outside night hours")
    parser.add_argument("--text", help="Text for TTS")
    parser.add_argument("--audio", help="Base64 audio for STT")
    args = parser.parse_args()
    
    # Check night hours (02:00-06:00) unless forced
    now = datetime.now()
    is_night = 2 <= now.hour < 6
    if not is_night and not args.force:
        print(f"[MUSICIAN] Не ночное время ({now.hour}:{now.minute:02d}). Запуск только 02:00-06:00. Используйте --force для принудительного запуска.")
        
        # Queue the task
        queue_file = ROOT / "queue" / "musician" / f"{args.project}.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue = []
        if queue_file.exists():
            queue = json.loads(queue_file.read_text())
        queue.append({
            "track_type": args.track_type,
            "project": args.project,
            "cycle": args.cycle,
            "text": args.text,
            "audio": args.audio,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending"
        })
        queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
        print(f"[MUSICIAN] Задача поставлена в очередь: {args.track_type}")
        return
    
    print(f"[MUSICIAN] Ночной запуск ({datetime.now().hour}:{datetime.now().minute:02d}) для {args.project} цикл {args.cycle}")
    
    queue_file = ROOT / "queue" / "musician" / f"{args.project}.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue = []
    if queue_file.exists():
        queue = json.loads(queue_file.read_text())
    
    pending = [t for t in queue if t["status"] == "pending"]
    
    # Add command-line task
    if args.track_type in ["ambient", "battle", "menu", "victory", "tts", "stt"]:
        pending.append({
            "track_type": args.track_type,
            "project": args.project,
            "cycle": args.cycle,
            "text": args.text,
            "audio": args.audio
        })
    
    if not pending:
        print("[MUSICIAN] Очередь пуста")
        return
    
    generated = []
    for task in pending:
        track_type = task["track_type"]
        audio_b64 = None
        provider = "unsloth-studio"
        
        if track_type in ["ambient", "battle", "menu", "victory"]:
            # Music generation
            prompts = {
                "ambient": "ambient atmospheric music, calm, evolving textures, no drums",
                "battle": "epic battle music, orchestral, intense, driving rhythm",
                "menu": "calm menu music, peaceful, looping, gentle melody",
                "victory": "victory fanfare, triumphant, uplifting, major key"
            }
            prompt = prompts.get(track_type, f"{track_type} music")
            duration = 60 if track_type == "ambient" else 30
            
            print(f"[MUSICIAN] Генерирую {track_type} через unsloth-studio ACE-Step...")
            audio_b64 = unsloth_musicgen(prompts[track_type], duration)
            
        elif track_type == "tts":
            text = task.get("text", "Привет, это тест TTS")
            print(f"[MUSICIAN] TTS: {text[:50]}...")
            audio_b64 = unsloth_tts(text)
            
        elif track_type == "stt":
            audio_input = task.get("audio")
            if audio_input:
                print(f"[MUSICIAN] STT расшифровка...")
                audio_b64 = unsloth_stt(audio_input)
            else:
                print("[MUSICIAN] ОШИБКА: Нет аудио для STT")
        
        if audio_b64:
            filepath = save_audio(args.project, track_type, audio_b64)
            generated.append({"type": track_type, "path": filepath})
            print(f"[MUSICIAN] Сгенерировано: {filepath}")
        else:
            print(f"[MUSICIAN] Не удалось сгенерировать {track_type}")
        
        time.sleep(1)
    
    emit_event("musician.done", {
        "project": args.project,
        "cycle": args.cycle,
        "status": "complete",
        "generated": generated
    })
    
    print(f"[MUSICIAN] Готово. Сгенерировано: {len(generated)} треков")

if __name__ == "__main__":
    main()