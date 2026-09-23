# HOT
#!/usr/bin/env python3
"""
Searcher Entry Point — Real LLM web research via Ollama/Lemonade
Called by searcher trigger, emits searcher.done event
"""

import argparse
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))

from model_selector import ModelSelector

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

def run_llm_ollama(model: str, prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True, text=True, timeout=180
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Ошибка: Таймаут"
    except Exception as e:
        return f"Ошибка: {e}"

def run_llm_lemonade(model: str, prompt: str) -> str:
    try:
        import requests
        resp = requests.post(
            "http://127.0.0.1:8000/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4096
            },
            timeout=120
        )
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Ошибка: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--topic", default="latest_ai_tools")
    args = parser.parse_args()
    
    print(f"[SEARCHER] Запуск цикла {args.cycle}, тема: {args.topic}")
    
    selector = ModelSelector()
    model_info = selector.get_model_for_task("research")
    if not model_info:
        print("[SEARCHER] ОШИБКА: Нет доступной модели")
        emit_event("searcher.done", {"cycle": args.cycle, "status": "error", "error": "No model"})
        sys.exit(1)
    
    ollama_models = selector.ollama_models
    lemonade_models = selector.lemonade_models
    
    if model_info in ollama_models:
        backend = "ollama"
    elif model_info in lemonade_models:
        backend = "lemonade"
    else:
        backend = "ollama"
    
    print(f"[SEARCHER] Используется модель: {model_info} (backend: {backend})")
    
    prompt = f"""Ты — исследователь в протоколе Living Code.

ЦИКЛ: {args.cycle}
ТЕМА: {args.topic}
ЗАДАЧА: Найти свежие, актуальные знания по теме

ИНСТРУКЦИИ:
1. Используй свои знания о последних разработках (до 2024)
2. Найди 3-5 ключевых находок/инсайтов
3. Для каждого: суть, почему важно, как применить
4. Укажи источники/ссылки где возможно

Формат ответа:
НАХОДКА_1: <суть> | ВАЖНОСТЬ: <почему> | ПРИМЕНЕНИЕ: <как>
НАХОДКА_2: ...
НАХОДКА_3: ...
...
РЕЗЮМЕ: <краткое итого>
"""
    
    print(f"[SEARCHER] Используется модель: {model_info} (backend: {backend})")
    print(f"[SEARCHER] Запуск LLM...")
    
    if backend == "lemonade":
        import requests
        try:
            resp = requests.post(
                "http://127.0.0.1:8000/v1/chat/completions",
                json={
                    "model": model_info,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 4096
                },
                timeout=120
            )
            response = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            response = f"Ошибка: {e}"
    else:
        result = subprocess.run(
            ["ollama", "run", model_info, prompt],
            capture_output=True, text=True, timeout=180
        )
        response = result.stdout.strip()
    
    print(f"[SEARCHER] Получен ответ LLM ({len(response)} символов)")
    
    emit_event("searcher.done", {
        "cycle": args.cycle,
        "topic": args.topic,
        "status": "complete",
        "model_used": model_info,
        "backend": backend,
        "findings": response[:2000]
    })
    
    print(f"[SEARCHER] Готово. Найдено знаний по теме: {args.topic}")

if __name__ == "__main__":
    main()