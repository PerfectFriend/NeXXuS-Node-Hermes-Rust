# HOT
#!/usr/bin/env python3
"""
Auditor Entry Point — Real LLM code review via Ollama/Lemonade
Called by auditor_trigger.py, emits auditor.done event
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
    event_file = EVENTS_DIR / f"{event_type}.{data.get('project','')}.cycle_{data.get('cycle',0)}.json"
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
                    "temperature": 0.1,
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
    args = parser.parse_args()
    
    print(f"[AUDITOR] Запуск ревью для {args.project} цикл {args.cycle}")
    
    selector = ModelSelector()
    model_info = selector.get_model_for_task("review")
    if not model_info:
        print("[AUDITOR] ОШИБКА: Нет доступной модели")
        emit_event("auditor.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "No model"})
        sys.exit(1)
    
    ollama_models = selector.ollama_models
    lemonade_models = selector.lemonade_models
    
    if model_info in ollama_models:
        backend = "ollama"
    elif model_info in lemonade_models:
        backend = "lemonade"
    else:
        backend = "ollama"
    
    print(f"[AUDITOR] Используется модель: {model_info} (backend: {backend})")
    
    project_path = ROOT / "Projects" / args.project
    if not project_path.exists():
        print(f"[AUDITOR] ОШИБКА: Проект не найден: {project_path}")
        emit_event("auditor.done", {"project": args.project, "cycle": args.cycle, "status": "error", "error": "Project not found"})
        sys.exit(1)
    
    # Collect changed files
    try:
        git_diff = subprocess.run(
            ["git", "diff", "HEAD~5..HEAD", "--", "*.py"],
            cwd=str(project_path), capture_output=True, text=True, timeout=30
        ).stdout
    except:
        git_diff = ""
    
    # Check for TODO/FIXME
    issues = []
    try:
        for f in project_path.rglob("*.py"):
            if f.is_file():
                content = f.read_text()
                if "TODO" in content or "FIXME" in content:
                    issues.append(f"{f.relative_to(project_path)}: есть TODO/FIXME")
    except:
        pass
    
    prompt = f"""Ты — аудитор кода в протоколе Living Code.

ПРОЕКТ: {args.project}
ЦИКЛ: {args.cycle}
ЗАДАЧА: Провести код-ревью недавних изменений

НЕДАВНИЕ ИЗМЕНЕНИЯ (git diff):
{git_diff if git_diff else "(нет недавних изменений)"}

НАЙДЕННЫЕ ПРОБЛЕМЫ (TODO/FIXME):
{chr(10).join(issues) if issues else "(нет явных TODO/FIXME)"}

ИНСТРУКЦИИ:
1. Проанализируй diff на предмет багов, стиля, безопасности
2. Проверь соответствие плану (PLAN.md)
3. Оцени качество: читаемость, тесты, документация
4. Вердикт: clean / issues_found / error

Формат ответа:
ВЕРДИКТ: clean|issues_found|error
ПРОБЛЕМЫ: <список найденных проблем или "нет">
РЕКОМЕНДАЦИИ: <что улучшить>
"""
    
    print(f"[AUDITOR] Используется модель: {model_info} (backend: {backend})")
    print(f"[AUDITOR] Запуск LLM...")
    
    try:
        selector = ModelSelector()
        model_info = selector.get_model_for_task("review")
    except:
        pass
    
    ollama_models = selector.ollama_models
    lemonade_models = selector.lemonade_models
    
    if model_info in ollama_models:
        backend = "ollama"
    elif model_info in lemonade_models:
        backend = "lemonade"
    else:
        backend = "ollama"
    
    response = run_llm(model_info, prompt, backend)
    print(f"[AUDITOR] Получен ответ LLM ({len(response)} символов)")
    
    status = "clean"
    if "ВЕРДИКТ: issues_found" in response:
        status = "issues_found"
    elif "ВЕРДИКТ: error" in response:
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
    
    emit_event("auditor.done", {
        "project": args.project,
        "cycle": args.cycle,
        "status": status,
        "model_used": model_info,
        "backend": backend,
        "hot_files_reviewed": hot_files,
        "issues_found": "issues_found" in status,
        "response_summary": response[:500]
    })
    
    print(f"[AUDITOR] Готово. Вердикт: {status}, Горячих файлов: {hot_files}")

if __name__ == "__main__":
    main()