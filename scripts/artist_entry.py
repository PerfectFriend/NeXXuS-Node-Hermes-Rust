# HOT
#!/usr/bin/env python3
"""
Artist Entry Point — Night batch image generation via free cloud APIs
Runs 02:00-06:00, processes accumulated queue
Uses: FAL (free tier), Pollinations (free), Replicate (free tier)
"""

import argparse
import json
import sys
import time
import requests
import base64
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR = ROOT / "queue" / "artist"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

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
    """Load pending tasks for project"""
    queue_file = QUEUE_DIR / f"{project}.json"
    if queue_file.exists():
        return json.loads(queue_file.read_text())
    return []

def save_queue(project: str, queue: list):
    """Save pending tasks for project"""
    queue_file = QUEUE_DIR / f"{project}.json"
    queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False))

def generate_pollinations(prompt: str, width: int = 1024, height: int = 1024) -> str:
    """Free Pollinations API - no key needed, generous limits"""
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        params = {"width": width, "height": height, "nologo": "true", "private": "true"}
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code == 200:
            img_b64 = base64.b64encode(resp.content).decode()
            return img_b64
    except Exception as e:
        print(f"[ARTIST] Pollinations error: {e}")
    return None

def generate_fal(prompt: str, model: str = "fal-ai/fast-sdxl") -> str:
    """FAL.ai - generous free tier (50/day)"""
    try:
        import os
        api_key = os.environ.get("FAL_KEY")
        if not api_key:
            return None
        
        resp = requests.post(
            f"https://fal.run/{model}",
            headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            json={"prompt": prompt, "image_size": "square_hd"},
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()
            if "images" in result and result["images"]:
                # Download image
                img_url = result["images"][0]["url"]
                img_resp = requests.get(img_url, timeout=30)
                img_b64 = base64.b64encode(img_resp.content).decode()
                return img_b64
    except Exception as e:
        print(f"[ARTIST] FAL error: {e}")
    return None

def generate_replicate(prompt: str) -> str:
    """Replicate - free tier available"""
    try:
        import os
        api_key = os.environ.get("REPLICATE_API_TOKEN")
        if not api_key:
            return None
            
        resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            json={
                "version": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                "input": {"prompt": prompt, "width": 1024, "height": 1024}
            },
            timeout=10
        )
        if resp.status_code == 201:
            prediction = resp.json()
            # Poll for result
            for _ in range(30):
                time.sleep(2)
                get_resp = requests.get(
                    f"https://api.replicate.com/v1/predictions/{prediction['id']}",
                    headers={"Authorization": f"Token {api_key}"}
                )
                if get_resp.status_code == 200:
                    result = get_resp.json()
                    if result["status"] == "succeeded" and result["output"]:
                        img_url = result["output"][0]
                        img_resp = requests.get(img_url, timeout=30)
                        return base64.b64encode(img_resp.content).decode()
                    elif result["status"] == "failed":
                        break
    except Exception as e:
        print(f"[ARTIST] Replicate error: {e}")
    return None

def save_image(project: str, asset_type: str, img_b64: str) -> str:
    """Save base64 image to project assets"""
    project_path = ROOT / "Projects" / project
    assets_dir = project_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{asset_type}_{timestamp}.png"
    filepath = assets_dir / filename
    
    img_data = base64.b64decode(img_b64)
    filepath.write_bytes(img_data)
    return str(filepath)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--assets", nargs="+", default=["banner", "icon", "splash"])
    parser.add_argument("--force", action="store_true", help="Run even outside night hours")
    args = parser.parse_args()
    
    # Check night hours (02:00-06:00) unless forced
    now = datetime.now()
    is_night = 2 <= now.hour < 6
    if not is_night and not args.force:
        print(f"[ARTIST] Не ночное время ({now.hour}:{now.minute:02d}). Запуск только 02:00-06:00. Используйте --force для принудительного запуска.")
        
        # Still accept tasks into queue
        queue = load_queue(args.project)
        for asset in args.assets:
            queue.append({
                "asset_type": asset,
                "project": args.project,
                "cycle": args.cycle,
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"
            })
        save_queue(args.project, queue)
        print(f"[ARTIST] Задачи поставлены в очередь: {args.assets}")
        return
    
    print(f"[ARTIST] Ночной запуск ({now.hour}:{now.minute:02d}) для {args.project} цикл {args.cycle}")
    
    # Load queue
    queue = load_queue(args.project)
    pending = [t for t in queue if t["status"] == "pending"]
    
    if not pending:
        # Also process command-line assets
        for asset in args.assets:
            pending.append({"asset_type": asset, "project": args.project, "cycle": args.cycle})
    
    if not pending:
        print("[ARTIST] Очередь пуста")
        return
    
    generated = []
    for task in pending:
        asset_type = task["asset_type"]
        
        # Build prompt based on asset type and project
        project_path = ROOT / "Projects" / task["project"]
        plan = ""
        if (project_path / "PLAN.md").exists():
            plan = (project_path / "PLAN.md").read_text()[:500]
        
        prompts = {
            "banner": f"Professional game banner for {task['project']}, {plan}, high quality, 16:9 aspect",
            "icon": f"App icon for {task['project']}, {plan}, clean, recognizable, 1:1 aspect",
            "splash": f"Splash screen for {task['project']}, {plan}, immersive, 16:9 aspect",
            "character": f"Character design for {task['project']}, {plan}, detailed, full body",
            "background": f"Background art for {task['project']}, {plan}, atmospheric, 16:9",
        }
        
        prompt = prompts.get(asset_type, f"{asset_type} for {task['project']}, {plan}")
        
        img_b64 = None
        # Try free providers in order
        for provider_func, name in [(generate_pollinations, "Pollinations"), 
                                     (generate_fal, "FAL"), 
                                     (generate_replicate, "Replicate")]:
            print(f"[ARTIST] Пробую {name} для {asset_type}...")
            img_b64 = provider_func(prompt)
            if img_b64:
                print(f"[ARTIST] Успех через {name}")
                break
            print(f"[ARTIST] {name} не сработал, пробую следующий...")
        
        if img_b64:
            filepath = save_image(task["project"], asset_type, img_b64)
            generated.append({"asset": asset_type, "path": filepath, "provider": name})
            task["status"] = "completed"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            task["path"] = filepath
        else:
            print(f"[ARTIST] Все провайдеры не сработали для {asset_type}")
            task["status"] = "failed"
        
        # Rate limiting
        time.sleep(2)
    
    # Update queue
    save_queue(args.project, queue)
    
    emit_event("artist.done", {
        "project": args.project,
        "cycle": args.cycle,
        "status": "complete",
        "generated": generated,
        "queue_remaining": len([t for t in queue if t["status"] == "pending"])
    })
    
    print(f"[ARTIST] Готово. Сгенерировано: {len(generated)}, в очереди: {len([t for t in queue if t['status'] == 'pending'])}")

if __name__ == "__main__":
    main()