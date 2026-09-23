# HOT
#!/usr/bin/env python3
"""
Task Executor — Runs on remote nodes (unsloth-studio, dell)
Receives tasks via HTTP, executes via Lemonade/Ollama, returns results.
"""

import json
import subprocess
import sys
import os
import base64
import tempfile
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

# Lemonade API base
LEMONADE_API = "http://127.0.0.1:8000/v1"

class TaskExecutor:
    def __init__(self):
        self.tasks = {}
    
    def execute(self, task: dict) -> dict:
        task_type = task.get("type")
        
        handlers = {
            "tts": self.handle_tts,
            "stt": self.handle_stt,
            "musicgen": self.handle_musicgen,
            "image_gen": self.handle_image_gen,
            "coder": self.handle_coder,
            "auditor": self.handle_auditor,
            "searcher": self.handle_searcher,
            "producer": self.handle_producer,
            "artist": self.handle_artist,
            "musician": self.handle_musician,
        }
        
        handler = handlers.get(task_type)
        if not handler:
            return {"error": f"Unknown task type: {task_type}"}
        
        try:
            return handler(task)
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}
    
    def handle_tts(self, task: dict) -> dict:
        """Text-to-Speech via kokoro-v1 or XTTS"""
        text = task.get("text", "")
        voice = task.get("voice", "kokoro-v1")
        language = task.get("language", "ru")
        
        try:
            import requests
            # Use Lemonade TTS endpoint
            resp = requests.post(
                f"{LEMONADE_API}/audio/speech",
                json={
                    "model": "kokoro-v1",
                    "input": text,
                    "voice": voice,
                    "response_format": "wav"
                },
                timeout=60
            )
            audio_data = resp.content
            
            # Save to temp file and return base64
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            with open(temp_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            os.unlink(temp_path)
            
            return {"success": True, "audio_base64": audio_b64, "format": "wav"}
        except Exception as e:
            return {"error": f"TTS failed: {e}"}
    
    def handle_stt(self, task: dict) -> dict:
        """Speech-to-Text via Whisper-Large-v3-Turbo"""
        audio_base64 = task.get("audio_base64")
        audio_path = task.get("audio_path")
        language = task.get("language", "ru")
        
        try:
            import requests
            
            if audio_base64:
                audio_data = base64.b64decode(audio_base64)
            elif audio_path and os.path.exists(audio_path):
                with open(audio_path, "rb") as f:
                    audio_data = f.read()
            else:
                return {"error": "No audio data provided"}
            
            # Save to temp file for upload
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            with open(temp_path, "rb") as f:
                files = {"file": (temp_path, f, "audio/wav")}
                data = {"model": "whisper-large-v3-turbo", "language": language}
                resp = requests.post(
                    f"{LEMONADE_API}/audio/transcriptions",
                    files=files,
                    data=data,
                    timeout=120
                )
            os.unlink(temp_path)
            
            return {"success": True, "text": resp.json().get("text", ""), "language": language}
        except Exception as e:
            return {"error": f"STT failed: {e}"}
    
    def handle_musicgen(self, task: dict) -> dict:
        """Music Generation via ACE-Step-Music"""
        prompt = task.get("prompt", "ambient electronic music")
        duration = task.get("duration", 30)
        
        try:
            import requests
            resp = requests.post(
                f"{LEMONADE_API}/audio/generations",
                json={
                    "model": "ACE-Step-Music",
                    "prompt": prompt,
                    "duration": duration
                },
                timeout=180
            )
            audio_data = resp.content
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            with open(temp_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            os.unlink(temp_path)
            
            return {"success": True, "audio_base64": audio_b64, "format": "wav"}
        except Exception as e:
            return {"error": f"MusicGen failed: {e}"}
    
    def handle_image_gen(self, task: dict) -> dict:
        """Image Generation via SDXL-Turbo or Flux"""
        prompt = task.get("prompt", "beautiful landscape")
        model = task.get("model", "SDXL-Turbo")
        
        try:
            import requests
            resp = requests.post(
                f"{LEMONADE_API}/images/generations",
                json={
                    "model": model,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024"
                },
                timeout=60
            )
            # Lemonade returns base64 or URL
            result = resp.json()
            
            # Handle both b64_json and url responses
            if "b64_json" in str(result):
                img_b64 = result["data"][0]["b64_json"]
            elif "url" in str(result):
                # Download from URL
                import requests as req
                img_data = req.get(result["data"][0]["url"]).content
                img_b64 = base64.b64encode(img_data).decode()
            else:
                return {"error": "Unexpected response format"}
            
            return {"success": True, "image_base64": img_b64, "format": "png"}
        except Exception as e:
            return {"error": f"ImageGen failed: {e}"}
    
    def handle_coder(self, task: dict) -> dict:
        project = task.get("project")
        cycle = task.get("cycle")
        return self.run_script("coder_entry.py", project, cycle)
    
    def handle_auditor(self, task: dict) -> dict:
        project = task.get("project")
        cycle = task.get("cycle")
        return self.run_script("auditor_entry.py", project, cycle)
    
    def handle_searcher(self, task: dict) -> dict:
        cycle = task.get("cycle", 0)
        topic = task.get("topic", "latest_ai_tools")
        return self.run_script("searcher_entry.py", cycle=cycle, topic=topic)
    
    def handle_producer(self, task: dict) -> dict:
        project = task.get("project")
        cycle = task.get("cycle")
        return self.run_script("producer_entry.py", project, cycle)
    
    def handle_artist(self, task: dict) -> dict:
        project = task.get("project")
        cycle = task.get("cycle")
        return self.run_script("artist_entry.py", project, cycle)
    
    def handle_musician(self, task: dict) -> dict:
        project = task.get("project")
        cycle = task.get("cycle")
        return self.run_script("musician_entry.py", project, cycle)
    
    def run_script(self, script: str, project: str = None, cycle: int = None, topic: str = None) -> dict:
        cmd = [sys.executable, f"scripts/{script}"]
        if project:
            cmd.extend(["--project", project])
        if cycle is not None:
            cmd.extend(["--cycle", str(cycle)])
        if topic:
            cmd.extend(["--topic", topic])
        
        try:
            result = subprocess.run(
                cmd, cwd="/home/thomas/LivingCode",
                capture_output=True, text=True, timeout=600
            )
            return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "Task timed out"}
        except Exception as e:
            return {"error": str(e)}

class TaskHandler(BaseHTTPRequestHandler):
    executor = TaskExecutor()
    
    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            task = json.loads(post_data.decode('utf-8'))
            
            result = self.executor.execute(task)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "node": "unsloth-studio"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default log messages
        pass

def run_server(port=8080):
    server = HTTPServer(('0.0.0.0', port), TaskHandler)
    print(f"Task Executor running on port {port}")
    print(f"Health check: http://localhost:{port}/health")
    print(f"Execute endpoint: http://localhost:{port}/execute")
    server.serve_forever()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)