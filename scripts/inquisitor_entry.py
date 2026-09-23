# HOT
#!/usr/bin/env python3
"""
Inquisitor Entry Point — Investigates issues, finds root causes, proposes fixes
Called by inquisitor_trigger.py, emits inquisitor.done event
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
    event_file = EVENTS_DIR / f"{event_type}.{data.get('project','')}.{data.get('issue','').replace(' ', '_')}.cycle_{data.get('cycle',0)}.json"
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
                timeout=180
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
    parser.add_argument("--issue", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", type=int, default=0)
    args = parser.parse_args()
    
    print(f"[INQUISITOR] Расследование: {args.issue} в проекте {args.project}")
    
    selector = ModelSelector()
    model_info = selector.get_model_for_task("review")  # Inquisitor uses strong reasoning model
    if not model_info:
        print("[INQUISITOR] ОШИБКА: Нет доступной модели")
        emit_event("inquisitor.done", {"issue": args.issue, "project": args.project, "cycle": args.cycle, "status": "error", "error": "No model"})
        sys.exit(1)
    
    ollama_models = selector.ollama_models
    lemonade_models = selector.lemonade_models
    
    if model_info in ollama_models:
        backend = "ollama"
    elif model_info in lemonade_models:
        backend = "lemonade"
    else:
        backend = "ollama"
    
    print(f"[INQUISITOR] Используется модель: {model_info} (backend: {backend})")
    
    project_path = ROOT / "Projects" / args.project
    if not project_path.exists():
        print(f"[INQUISITOR] ОШИБКА: Проект не найден: {project_path}")
        emit_event("inquisitor.done", {"issue": args.issue, "project": args.project, "cycle": args.cycle, "status": "error", "error": "Project not found"})
        sys.exit(1)
    
    # Collect context: git log, recent changes, error logs
    try:
        git_log = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            cwd=str(project_path), capture_output=True, text=True, timeout=10
        ).stdout
    except:
        git_log = ""
    
    try:
        git_diff = subprocess.run(
            ["git", "diff", "HEAD~10..HEAD"],
            cwd=str(project_path), capture_output=True, text=True, timeout=10
        ).stdout
    except:
        git_diff = ""
    
    # Check for error logs
    error_logs = ""
    for log_file in project_path.rglob("*.log"):
        try:
            content = log_file.read_text()[-2000:]
            if "error" in content.lower() or "exception" in content.lower() or "traceback" in content.lower():
                error_logs += f"\n--- {log_file.relative_to(project_path)} ---\n{content}"
        except:
            pass
    
    prompt = f"""Ты — Инквизитор в протоколе Living Code. Твоя задача — расследовать проблему, найти корневую причину и предложить исправление.

ПРОЕКТ: {args.project}
ПРОБЛЕМА: {args.issue}
ЦИКЛ: {args.cycle}

КОНТЕКСТ (git log -20):
{git_log if git_log else "(нет)"}

НЕДАВНИЕ ИЗМЕНЕНИЯ (git diff HEAD~10..HEAD):
{git_diff if git_diff else "(нет)"}

ЛОГИ ОШИБОК (если есть):
{error_logs if error_logs else "(нет явных ошибок в логах)"}

ЗАДАЧА:
1. Проанализируй проблему и контекст
2. Найди корневую причину (root cause)
3. Предложи конкретное исправление (файлы, строки, код)
4. Оцени риск и влияние исправления

ФОРМАТ ОТВЕТА:
## Корневая причина
<подробное описание root cause>

## Затрагиваемые файлы
- файл1.py: строка X
- файл2.py: строка Y

## Предлагаемое исправление
```python
# код до
# код после
```

## Риск исправления
- Риск: низкий/средний/высокий
- Влияние: какие компоненты затронуты

## План проверки
1. Шаг 1
2. Шаг 2

## Резюме для Супервайзера
<краткое резюме для принятия решения>
"""
    
    print(f"[INQUISITOR] Используется модель: {model_info} (backend: {backend})")
    print(f"[INQUISITOR] Запуск LLM...")
    
    response = run_llm(model_info, prompt, backend)
    print(f"[INQUISITOR] Получен ответ LLM ({len(response)} символов)")
    
    # Parse status from response
    status = "investigated"
    if "РЕШЕНО" in response or "ИСПРАВЛЕНО" in response:
        status = "resolved"
    elif "ТРЕБУЕТСЯ_РУЧНОЕ_ВМЕШАТЕЛЬСТВО" in response:
        status = "needs_manual"
    
    emit_event("inquisitor.done", {
        "issue": args.issue,
        "project": args.project,
        "cycle": args.cycle,
        "status": status,
        "model_used": model_info,
        "backend": backend,
        "investigation": response[:3000],
        "root_cause": response.split("## Корневая причина")[1].split("##")[0][:500] if "## Корневая причина" in response else ""
    })
    
    print(f"[INQUISITOR] Готово. Статус: {status}")

if __name__ == "__main__":
    main()