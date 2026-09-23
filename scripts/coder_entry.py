# HOT
#!/usr/bin/env python3
"""
Coder Entry Point — Real LLM implementation via Ollama/Lemonade
Called by coder_trigger.py, emits coder.done event
"""

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/thomas/LivingCode")
EVENTS_DIR = ROOT / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))

from model_selector import ModelSelector

def emit_event(event_type, data):
    """Emit event to events/ directory"""
    event = {
        "type": event_type,
        **data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    event_file = EVENTS_DIR / f"{event_type}.{data.get('project','')}.cycle_{data.get('cycle',0)}.json"
    temp = event_file.with_suffix(".tmp")
    temp.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    temp.rename(event_file)

def run_llm(model: str, prompt: str, backend: str = "ollama") -> str:
    """Run LLM via Ollama or Lemonade"""
    if backend == "lemonade":
        try:
            import requests
            resp = requests.post(
                "http://127.0.0.1:8000/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 4096
                },
                timeout=120
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Ошибка: {e}"
    else:
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--task", default="implement")
    args = parser.parse_args()
    
    print(f"[CODER] Запуск цикла {args.cycle} для {args.project}")
    
    selector = ModelSelector()
    model_info = selector.get_model_for_task("code")
    if not model_info:
        print("[CODER] ОШИБКА: Нет доступной модели")
        emit_event("coder.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "No model", "hot_files": 0})
        sys.exit(1)
    
    ollama_models = selector.ollama_models
    lemonade_models = selector.lemonade_models
    
    if model_info in ollama_models:
        backend = "ollama"
    elif model_info in lemonade_models:
        backend = "lemonade"
    else:
        backend = "ollama"
    
    print(f"[CODER] Используется модель: {model_info} (backend: {backend})")
    
    project_path = ROOT / "Projects" / args.project
    if not project_path.exists():
        print(f"[CODER] ОШИБКА: Проект не найден: {project_path}")
        emit_event("coder.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "Project not found", "hot_files": 0})
        sys.exit(1)
    
    plan_file = project_path / "PLAN.md"
    plan = plan_file.read_text() if plan_file.exists() else ""
    
    try:
        git_diff = subprocess.run(
            ["git", "diff", "HEAD~5..HEAD", "--", "*.py"],
            cwd=str(project_path), capture_output=True, text=True, timeout=30
        ).stdout
    except:
        git_diff = ""
    
    prompt = f"""Ты — старший разработчик в протоколе Living Code.

ПРОЕКТ: {args.project}
ЦИКЛ: {args.cycle}
ЗАДАЧА: Реализовать задачи из PLAN.md

ТЕКУЩИЙ ПЛАН:
{plan if plan else "(пусто)"}

НЕДАВНИЕ ИЗМЕНЕНИЯ (git diff):
{git_diff if git_diff else "(нет недавних изменений)"}

ИНСТРУКЦИИ:
1. Прочитай PLAN.md и найди непомеченные пункты (- [ ])
2. Реализуй ОДНУ логическую задачу из плана
3. Пиши чистый, тестированный Python код
4. Следуй стилю кода в проекте
5. Верни краткое резюме того, что реализовал

Формат ответа:
РЕАЛИЗОВАНО: <что сделал>
ИЗМЕНЁННЫЕ_ФАЙЛЫ: <список файлов>
СТАТУС: partial|complete|error
"""
    
    print(f"[CODER] Запуск LLM...")
    response = run_llm(model_info, prompt, backend)
    print(f"[CODER] Получен ответ LLM ({len(response)} символов)")
    
    status = "partial"
    if "СТАТУС: complete" in response:
        status = "complete"
    elif "СТАТУС: error" in response:
        status = "error"
    
    hot_files = 0
    try:
        import time
        now = time.time()
        for f in project_path.rglob("*.py"):
            if f.is_file() and (now - f.stat().st_mtime) < 3600:
                hot_files += 1
    except:
        pass
    
    emit_event("coder.done", {
        "project": args.project,
        "cycle": args.cycle,
        "status": status,
        "model_used": model_info,
        "backend": backend,
        "hot_files": hot_files,
        "response_summary": response[:500]
    })
    
    print(f"[CODER] Готово. Статус: {status}, Горячих файлов: {hot_files}")

if __name__ == "__main__":
    main()