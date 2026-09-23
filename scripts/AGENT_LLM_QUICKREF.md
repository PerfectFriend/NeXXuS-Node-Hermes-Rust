# Living Code Protocol — Agent Quick Reference: Local LLM (llama.cpp)

## 🚀 Quick Commands for Agents

### Direct Python call (recommended)
```bash
# Simple prompt
python3 /home/thomas/LivingCode/scripts/llm_local.py "Write a Python class for async HTTP client with retry"

# With system prompt
python3 /home/thomas/LivingCode/scripts/llm_local.py \
  --system "You are a code generator. Output only code, no markdown, no explanations." \
  "Python async HTTP client with retry"

# From stdin (for long prompts)
cat prompt.txt | python3 /home/thomas/LivingCode/scripts/llm_local.py

# JSON output for parsing
python3 /home/thomas/LivingCode/scripts/llm_local.py --json "Write fibonacci function"
```

### Direct curl (no Python deps)
```bash
curl -s -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder-v2-16b",
    "messages": [
      {"role": "system", "content": "You are a code generator. Output only code."},
      {"role": "user", "content": "Write a Python fibonacci function"}
    ],
    "temperature": 0.1,
    "max_tokens": 4000
  }' | jq -r '.choices[0].message.content'
```

### Health check before use
```bash
python3 /home/thomas/LivingCode/scripts/llm_local.py --health
# Returns: ✅ llama.cpp server is healthy  (exit 0)
# Or:      ❌ llama.cpp server is not responding  (exit 1)
```

## ⚙️ Model Parameters (tuned for code)
| Parameter | Value | Why |
|-----------|-------|-----|
| `temperature` | 0.1 | Deterministic, consistent code |
| `max_tokens` | 8000 | Large outputs for full files |
| `context` | 160,000 | Huge files fit with history |

## 🔧 Environment Variables (optional override)
```bash
export LLAMA_CPP_URL="http://localhost:8081/v1/chat/completions"
export LLAMA_CPP_MODEL="deepseek-coder-v2-16b"
```

## ⚠️ Common Issues
| Problem | Fix |
|---------|-----|
| "Connection refused" | `sudo systemctl start llama-server.service` |
| Timeout | Increase `--timeout` (default 120s) |
| Empty response | Check `max_tokens` not too low |
| Garbled output | Use `--system "Output only code, no markdown"` |

## 📋 Agent Integration Pattern
```python
#!/usr/bin/env python3
import subprocess
import sys

def generate_code(prompt: str, system: str = None) -> str:
    """Call local LLM for code generation."""
    cmd = [sys.executable, "/home/thomas/LivingCode/scripts/llm_local.py"]
    if system:
        cmd.extend(["--system", system])
    cmd.append(prompt)
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"LLM failed: {result.stderr}")
    return result.stdout.strip()

# Usage in agent:
code = generate_code(
    "Write a Python class for database connection pooling",
    system="You are a senior Python developer. Output only clean, production-ready code with type hints."
)
```

## ✅ Verification Checklist (run at agent startup)
- [ ] `python3 /home/thomas/LivingCode/scripts/llm_local.py --health` → OK
- [ ] `curl -s http://localhost:8081/health` → `{"status":"ok"}`
- [ ] Test generation works in < 5 seconds

---

**Model:** deepseek-coder-v2-16b (Q4_0, 8.9 GB)  
**Backend:** llama.cpp on Radeon 780M (Vulkan/RADV)  
**Throughput:** ~19-25 tok/s  
**Context:** 160,000 tokens native