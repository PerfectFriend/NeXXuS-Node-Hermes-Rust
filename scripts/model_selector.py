#!/usr/bin/env python3
"""
Model Selector — chooses best available model for agent role
with fallback chain from fallback_chains.yaml
Supports Ollama + Lemonade backends
"""

import yaml
import subprocess
import json
import requests
from pathlib import Path

REGISTRY = Path("/home/thomas/LivingCode/model_registry.local.json")
FALLBACK_CHAINS = Path("/home/thomas/LivingCode/fallback_chains.yaml")

class ModelSelector:
    def __init__(self):
        self.registry = self.load_registry()
        self.chains = self.load_chains()
        self.ollama_models = self.get_ollama_models()
        self.lemonade_models = self.get_lemonade_models()
        self.all_models = self.ollama_models + self.lemonade_models
    
    def load_registry(self):
        if REGISTRY.exists():
            return json.loads(REGISTRY.read_text())
        return {"ollama_models": [], "lemonade_models": []}
    
    def load_chains(self):
        if FALLBACK_CHAINS.exists():
            return yaml.safe_load(FALLBACK_CHAINS.read_text())
        return {"chains": {}, "node_overrides": {}}
    
    def get_ollama_models(self):
        """Get actually installed Ollama models"""
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            models = []
            for line in result.stdout.strip().split('\n')[1:]:  # skip header
                if line.strip():
                    name = line.split()[0]
                    models.append(name)
            return models
        except:
            return []
    
    def get_lemonade_models(self):
        """Get actually installed Lemonade models"""
        try:
            result = subprocess.run(["lemonade", "list"], capture_output=True, text=True)
            models = []
            in_local = False
            for line in result.stdout.strip().split('\n'):
                if "Local" in line:
                    in_local = True
                    continue
                if "Available for Download" in line:
                    in_local = False
                    continue
                if in_local and line.strip() and not line.startswith("-"):
                    # Parse: Model Name    Downloaded    Size    Details
                    parts = line.split()
                    if parts and parts[1] == "Yes":
                        models.append(parts[0])
            return models
        except:
            return []
    
    def is_model_available(self, model_name):
        """Check if model is installed in Ollama OR Lemonade"""
        return model_name in self.all_models
    
    def get_best_model(self, agent_role, node_id="totomoto"):
        """Get best available model for agent role with fallback"""
        # Check node-specific override first
        overrides = self.chains.get("node_overrides", {}).get(node_id, {})
        chain = overrides.get(agent_role)
        
        if not chain:
            chain = self.chains.get("chains", {}).get(agent_role, [])
        
        if not chain:
            chain = self.chains.get("chains", {}).get("general", [])
        
        # Try each model in chain
        for model in chain:
            if self.is_model_available(model):
                return model
        
        # Fallback: any available model
        if self.all_models:
            return self.all_models[0]
        
        return None
    
    def get_model_for_task(self, task_type):
        """Map task type to agent role"""
        mapping = {
            "code": "coder",
            "review": "auditor",
            "research": "searcher",
            "learn": "professor",
            "art": "artist",
            "music": "musician",
            "tts": "tts",
            "stt": "stt",
            "image_gen": "image_gen",
            "music_gen": "music_gen",
        }
        role = mapping.get(task_type, "general")
        return self.get_best_model(role)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", help="Agent role (coder, auditor, searcher, etc.)")
    parser.add_argument("--task", help="Task type (code, review, research, etc.)")
    parser.add_argument("--node", default="totomoto", help="Node ID")
    parser.add_argument("--list", action="store_true", help="List all available models")
    args = parser.parse_args()
    
    selector = ModelSelector()
    
    if args.list:
        print("Available Ollama models:")
        for m in selector.ollama_models:
            print(f"  {m}")
        print("\nAvailable Lemonade models:")
        for m in selector.lemonade_models:
            print(f"  {m}")
        print("\nFallback chains:")
        for role, chain in selector.chains.get("chains", {}).items():
            print(f"  {role}: {' -> '.join(chain)}")
        return
    
    if args.role:
        model = selector.get_best_model(args.role, args.node)
        print(model or "NO_MODEL_AVAILABLE")
    elif args.task:
        model = selector.get_model_for_task(args.task)
        print(model or "NO_MODEL_AVAILABLE")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()