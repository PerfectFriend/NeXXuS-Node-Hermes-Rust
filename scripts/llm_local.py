#!/home/thomas/bin/python3
"""
Living Code Protocol - Local LLM Client
Simple wrapper for agents to use llama.cpp server directly via HTTP API.
Bypasses Hermes CLI issues with llamacpp provider.

Usage:
    python3 llm_local.py "Write a Python fibonacci function"
    python3 llm_local.py --system "You are a code generator" --prompt "Write async HTTP client"
    echo "prompt" | python3 llm_local.py
"""

import sys
import json
import argparse
import os
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Installing httpx...", file=sys.stderr)
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
    import httpx


# Configuration
LLAMA_CPP_URL = os.environ.get("LLAMA_CPP_URL", "http://localhost:8081/v1/chat/completions")
MODEL = os.environ.get("LLAMA_CPP_MODEL", "deepseek-coder-v2-16b")
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 8000
DEFAULT_TIMEOUT = 120.0


def call_llama_cpp(
    prompt: str,
    system: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Call llama.cpp server via OpenAI-compatible API."""
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                LLAMA_CPP_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise ValueError(f"Unexpected response format: {data}")
                
    except httpx.TimeoutException:
        raise RuntimeError(f"Request timed out after {timeout}s")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"Failed to call llama.cpp: {e}")


def health_check() -> bool:
    """Check if llama.cpp server is healthy."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(LLAMA_CPP_URL.replace("/v1/chat/completions", "/health"))
            return response.status_code == 200 and response.json().get("status") == "ok"
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Living Code Protocol - Local LLM Client (llama.cpp)"
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to send to the model")
    parser.add_argument("--system", "-s", help="System prompt")
    parser.add_argument("--temperature", "-t", type=float, default=DEFAULT_TEMPERATURE, help="Temperature (default: 0.1)")
    parser.add_argument("--max-tokens", "-m", type=int, default=DEFAULT_MAX_TOKENS, help="Max tokens (default: 8000)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Timeout in seconds (default: 120)")
    parser.add_argument("--health", action="store_true", help="Check server health and exit")
    parser.add_argument("--json", action="store_true", help="Output raw JSON response")
    
    args = parser.parse_args()
    
    if args.health:
        if health_check():
            print("✅ llama.cpp server is healthy")
            sys.exit(0)
        else:
            print("❌ llama.cpp server is not responding")
            sys.exit(1)
    
    # Read prompt from stdin if not provided as argument
    if args.prompt is None:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        args.prompt = sys.stdin.read().strip()
    
    if not args.prompt:
        print("Error: Empty prompt", file=sys.stderr)
        sys.exit(1)
    
    try:
        result = call_llama_cpp(
            prompt=args.prompt,
            system=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout
        )
        
        if args.json:
            print(json.dumps({"response": result}, ensure_ascii=False))
        else:
            print(result)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()