# HOT
#!/usr/bin/env python3
"""
Professor Entry Point — Deep technical learning & knowledge synthesis
Called by professor_trigger.py, emits professor.done event
"""

import argparse
import json
import subprocess
import sys
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
    event_file = EVENTS_DIR / f"{event_type}.{data.get('topic','').replace(' ', '_')}.cycle_{data.get('cycle',0)}.json"
    temp = event_file.with_suffix(".tmp")
    temp.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp.rename(event_file)

def run_llm(model: str, prompt: str, backend: str = "ollama") -> str:
    if backend == "lemonade":
        try:
            import requests
            resp = requests.post(
                "http://127.0.0.1:8000/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 8192
                },
                timeout=180
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Ошибка: {e}"
    else:
        try:
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True, text=True, timeout=300
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Ошибка: Таймаут"
        except Exception as e:
            return f"Ошибка: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--priority", default="normal", choices=["low", "normal", "high", "urgent"])
    parser.add_argument("--cycle", type=int, default=0)
    args = parser.parse_args()
    
    print(f"[PROFESSOR] Изучение темы: {args.topic} (приоритет: {args.priority})")
    
    selector = ModelSelector()
    model_info = selector.get_model_for_task("learn")
    if not model_info:
        print("[PROFESSOR] ОШИБКА: Нет доступной модели")
        emit_event("professor.done", {"topic": args.topic, "cycle": args.cycle, "status": "error", "error": "No model"})
        sys.exit(1)
    
    ollama_models = selector.ollama_models
    lemonade_models = selector.lemonade_models
    
    if model_info in ollama_models:
        backend = "ollama"
    elif model_info in lemonade_models:
        backend = "lemonade"
    else:
        backend = "ollama"
    
    print(f"[PROFESSOR] Используется модель: {model_info} (backend: {backend})")
    
    # Check existing knowledge base
    kb_path = ROOT / "knowledge-base" / args.topic.replace(" ", "_").replace("/", "_")
    existing = ""
    if kb_path.exists():
        existing = kb_path.read_text()[:2000]
    
    prompt = f"""Ты — Профессор в протоколе Living Code. Твоя задача — глубоко изучить тему и создать качественную базу знаний.

ТЕМА: {args.topic}
ПРИОРИТЕТ: {args.priority}
ЦИКЛ: {args.cycle}

СУЩЕСТВУЮЩИЕ ЗНАНИЯ (если есть):
{existing if existing else "(пусто)"}

ЗАДАЧА:
1. Глубоко изучи тему, используй свои знания (до 2024)
2. Структурируй знания: ключевые концепции, архитектура, лучшие практики, типичные ошибки
3. Дай конкретные примеры кода/конфигурации где уместно
4. Укажи ссылки на официальные доки, статьи, репозитории
5. Создай структурированную базу знаний для других агентов

ФОРМАТ ОТВЕТА:
# {args.topic}

## Ключевые концепции
- Концепция 1: описание
- Концепция 2: описание

## Архитектура / Принципы работы
...

## Лучшие практики
- Практика 1
- Практика 2

## Типичные ошибки и как избежать
- Ошибка 1: как избежать
- Ошибка 2: как избежать

## Примеры кода / Конфигурации
```python
# пример
```

## Полезные ссылки
- [Официальная документация](URL)
- [Статья/Репозиторий](URL)

## Резюме для агентов
<краткое резюме для быстрого понимания другими агентами>
"""
    
    print(f"[PROFESSOR] Используется модель: {model_info} (backend: {backend})")
    print(f"[PROFESSOR] Запуск LLM...")
    
    response = run_llm(model_info, prompt, backend)
    print(f"[PROFESSOR] Получен ответ LLM ({len(response)} символов)")
    
    # Save to knowledge base
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    kb_path.write_text(response, encoding="utf-8")
    
    emit_event("professor.done", {
        "topic": args.topic,
        "priority": args.priority,
        "cycle": args.cycle,
        "status": "complete",
        "model_used": model_info,
        "backend": backend,
        "knowledge_path": str(kb_path),
        "response_summary": response[:500]
    })
    
    print(f"[PROFESSOR] Готово. База знаний сохранена: {kb_path}")

if __name__ == "__main__":
    main()