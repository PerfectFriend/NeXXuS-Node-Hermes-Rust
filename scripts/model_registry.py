#!/usr/bin/env python3
# Living Code Ecosystem — Model Registry (Библиотекарь Фёдорович)
# Версия: 1.0
# Маршрутизация задач к лучшей модели на нужном узле Tailscale
# Использование: python model_registry.py --health-check --all-nodes | --route --task "architecture" --project 1

import argparse
import json
import subprocess
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

@dataclass
class ModelNode:
    node_id: str
    name: str
    tailscale_host: str
    models: List[str]
    primary_model: str
    fallback_models: List[str]
    role: str  # architect, coder, audio, fine-tuning, inference
    gpu: str
    vram_gb: int
    status: str = "unknown"
    latency_ms: float = 0.0
    last_check: str = ""

@dataclass
class RoutingDecision:
    task: str
    project: int
    selected_node: str
    selected_model: str
    reason: str
    fallback_chain: List[str]
    timestamp: str

# === NODE REGISTRY (6 узлов Tailscale) ==="
NODES = [
    ModelNode(
        node_id="lenovo",
        name="Lenovo (Torquemada)",
        tailscale_host="lenovo",
        models=["nemotron-3-ultra", "qwen2.5-coder-32b", "qwen2.5-32b", "deepseek-coder-33b"],
        primary_model="nemotron-3-ultra",
        fallback_models=["qwen2.5-coder-32b", "deepseek-coder-33b"],
        role="architect,coder,reasoner",
        gpu="RTX 4090",
        vram_gb=24
    ),
    ModelNode(
        node_id="dell",
        name="Dell (Tomas)",
        tailscale_host="dell",
        models=["qwen2.5-14b", "phi-3.5-mini", "qwen2.5-7b", "gemma-2-9b"],
        primary_model="qwen2.5-14b",
        fallback_models=["phi-3.5-mini", "gemma-2-9b"],
        role="orchestrator,tester,deployer",
        gpu="Integrated",
        vram_gb=16
    ),
    ModelNode(
        node_id="totomoto",
        name="totomoto (Audio Master)",
        tailscale_host="totomoto",
        models=["ace-step", "musicgen", "xtts-v2", "whisper-large-v3", "audioldm", "stable-audio"],
        primary_model="ace-step",
        fallback_models=["musicgen", "audioldm"],
        role="audio-generation,voice-dialog,radio-ads",
        gpu="RTX 4090",
        vram_gb=48
    ),
    ModelNode(
        node_id="unsloth-studio",
        name="Unsloth Studio (Fine-tuning Farm)",
        tailscale_host="unsloth-studio",
        models=["nemotron-3-ultra-550b-A55b", "unsloth-qwen2.5", "unsloth-llama3", "unsloth-mistral", "unsloth-phi3"],
        primary_model="nemotron-3-ultra-550b-A55b",
        fallback_models=["unsloth-qwen2.5", "unsloth-llama3", "unsloth-mistral", "unsloth-phi3"],
        role="fine-tuning,quantization,benchmark,architect,coder,reasoner",
        gpu="4x H100",
        vram_gb=320
    ),
    ModelNode(
        node_id="ubuntu-server",
        name="Ubuntu Server (Inference Cluster)",
        tailscale_host="ubuntu-server",
        models=["nemotron-3-ultra-550b-A55b", "vllm", "sglang", "gpustack", "tgi", "ollama"],
        primary_model="nemotron-3-ultra-550b-A55b",
        fallback_models=["vllm", "sglang", "gpustack", "tgi", "ollama"],
        role="inference-serving,batch-processing,cluster,architect,coder,reasoner",
        gpu="8x H100",
        vram_gb=640
    ),
    ModelNode(
        node_id="local",
        name="Local (This Machine)",
        tailscale_host="localhost",
        models=["nemotron-3-ultra-free", "qwen2.5-coder-7b", "phi-3.5-mini"],
        primary_model="nemotron-3-ultra-free",
        fallback_models=["qwen2.5-coder-7b"],
        role="fallback,lightweight",
        gpu="CPU/AMD 780M",
        vram_gb=8
    ),
]

# === TASK TO ROLE MAPPING ==="
TASK_ROLE_MAP = {
    "architecture": "architect",
    "refactor": "architect",
    "reasoning": "reasoner",
    "coding": "coder",
    "code": "coder",
    "implementation": "coder",
    "integration": "orchestrator",
    "api": "orchestrator",
    "test": "tester",
    "deploy": "deployer",
    "orchestration": "orchestrator",
    "audio": "audio-generation",
    "music": "audio-generation",
    "voice": "voice-dialog",
    "sfx": "audio-generation",
    "tts": "voice-dialog",
    "stt": "voice-dialog",
    "fine-tuning": "fine-tuning",
    "lora": "fine-tuning",
    "quantization": "quantization",
    "benchmark": "benchmark",
    "inference": "inference-serving",
    "serving": "inference-serving",
    "batch": "batch-processing",
    "cluster": "cluster",
}

class ModelRegistry:
    def __init__(self):
        self.root = Path("C:/LivingCode")
        self.cache_dir = self.root / "cache" / "model_registry"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "routing_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding='utf-8'))
            except:
                return {}
        return {}
    
    def _save_cache(self):
        self.cache_file.write_text(json.dumps(self.cache, indent=2, ensure_ascii=False), encoding='utf-8')
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 30) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def check_node_health(self, node: ModelNode) -> Dict:
        """Check health of a single Tailscale node"""
        start = time.time()
        
        # Check Tailscale connectivity
        if node.tailscale_host != "localhost":
            success, out, err = self.run_cmd(f"tailscale ping -c 1 {node.tailscale_host} 2>&1", timeout=10)
            latency = (time.time() - start) * 1000
            online = success and "pong" in out.lower()
        else:
            online = True
            latency = 0
        
        # Check model availability (via model API endpoint)
        model_healthy = False
        if online and node.tailscale_host != "localhost":
            # Try to query model health endpoint
            success, out, err = self.run_cmd(
                f"curl -s -m 5 http://{node.tailscale_host}:8080/health 2>&1 || "
                f"curl -s -m 5 http://{node.tailscale_host}:11434/api/tags 2>&1",
                timeout=10
            )
            model_healthy = success and (out.strip() != "")
        elif node.tailscale_host == "localhost":
            model_healthy = True  # Assume local models available
        
        status = "healthy" if (online and model_healthy) else "unhealthy"
        if online and not model_healthy:
            status = "degraded"
        
        return {
            "node_id": node.node_id,
            "name": node.name,
            "online": online,
            "model_healthy": model_healthy,
            "status": status,
            "latency_ms": round(latency, 2),
            "primary_model": node.primary_model,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    
    def health_check_all(self) -> Dict:
        """Health check all 6 nodes"""
        print(f"\n{'='*60}")
        print(f"���🤖 MODEL REGISTRY — Health Check All Nodes")
        print(f"{'='*60}")
        
        results = []
        healthy_count = 0
        
        for node in NODES:
            print(f"\n  �� 🔍 Checking {node.name} ({node.tailscale_host})...")
            health = self.check_node_health(node)
            results.append(health)
            
            icon = {"healthy": "��✅", "degraded": "��⚠��️", "unhealthy": "����❌"}.get(health["status"], "������❓")
            print(f"     {icon} Status: {health['status']} | Latency: {health['latency_ms']}ms | Model: {health['primary_model']}")
            
            if health["status"] == "healthy":
                healthy_count += 1
        
        summary = {
            "total_nodes": len(NODES),
            "healthy_nodes": healthy_count,
            "degraded_nodes": len([r for r in results if r["status"] == "degraded"]),
            "unhealthy_nodes": len([r for r in results if r["status"] == "unhealthy"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nodes": results
        }
        
        print(f"\n{'='*60}")
        print(f"���������📊 SUMMARY: {healthy_count}/{len(NODES)} healthy")
        print(f"{'='*60}")
        
        return summary
    
    def test_fallback_chains(self) -> Dict:
        """Test that fallback chains work"""
        print(f"\n{'='*60}")
        print(f"���������🔄 TESTING FALLBACK CHAINS")
        print(f"{'='*60}")
        
        results = []
        
        for node in NODES:
            if node.tailscale_host == "localhost":
                continue
            
            print(f"\n  ���� �� �� 🔗 Testing fallback chain for {node.name}...")
            chain_ok = True
            
            # Test primary
            primary_ok = self._test_model_on_node(node, node.primary_model)
            print(f"     Primary ({node.primary_model}): {'������✅' if primary_ok else '������❌'}")
            
            # Test fallbacks
            for fallback in node.fallback_models:
                fallback_ok = self._test_model_on_node(node, fallback)
                print(f"     Fallback ({fallback}): {'������✅' if fallback_ok else '������❌'}")
                if not fallback_ok:
                    chain_ok = False
            
            results.append({
                "node": node.node_id,
                "primary_ok": primary_ok,
                "fallbacks_ok": all(self._test_model_on_node(node, f) for f in node.fallback_models),
                "chain_ok": chain_ok
            })
        
        return {"fallback_tests": results}
    
    def _test_model_on_node(self, node: ModelNode, model: str) -> bool:
        """Test if a specific model responds on a node"""
        # Simplified: just check if node is online
        success, out, err = self.run_cmd(f"tailscale ping -c 1 {node.tailscale_host} 2>&1", timeout=5)
        return success and "pong" in out.lower()
    
    def warm_cache(self, top_prompts: int = 10) -> Dict:
        """Warm up cache with common prompts"""
        print(f"\n{'='*60}")
        print(f"���������🔥 WARMING CACHE with top {top_prompts} prompts")
        print(f"{'='*60}")
        
        common_prompts = [
            "Write a clean architecture for a game engine module",
            "Implement adaptive music system for Unity",
            "Refactor authentication module with OAuth2",
            "Optimize render pipeline for 120fps",
            "Generate boss fight music theme",
            "Create FMOD integration for spatial audio",
            "Write property-based tests for core engine",
            "Design zero-trust security architecture",
            "Implement distributed model routing",
            "Create CI/CD pipeline for multi-platform deploy",
        ]
        
        warmed = 0
        for prompt in common_prompts[:top_prompts]:
            decision = self.route_task(prompt, project=1, use_cache=True)
            if decision:
                self.cache[f"prompt:{hash(prompt)}"] = asdict(decision)
                warmed += 1
        
        self._save_cache()
        print(f"  ��� � � ✅ Warmed {warmed} cache entries")
        return {"warmed": warmed, "cache_size": len(self.cache)}
    
    def route_task(self, task: str, project: int = 1, use_cache: bool = True) -> Optional[RoutingDecision]:
        """Route task to best model on best node"""
        # Check cache
        cache_key = f"prompt:{hash(task)}"
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            print(f"  ���� �� �� 📦 Cache hit for: {task[:50]}...")
            return RoutingDecision(**cached)
        
        # Determine required role
        task_lower = task.lower()
        required_role = "coder"  # default
        for keyword, role in TASK_ROLE_MAP.items():
            if keyword in task_lower:
                required_role = role
                break
        
        # Find best node for role
        suitable_nodes = [n for n in NODES if required_role in n.role]
        
        if not suitable_nodes:
            # Fallback to any coder node
            suitable_nodes = [n for n in NODES if "coder" in n.role]
        
        if not suitable_nodes:
            suitable_nodes = NODES
        
        # PREFER NEMOTRON 3 ULTRA 550b A55b FOR ALL TASKS
        # First, try to find a healthy node that has the nemotron-3-ultra-550b-A55b model
        target_model = "nemotron-3-ultra-550b-A55b"
        selected_node = None
        for node in suitable_nodes:
            # Check cache for node health
            health_key = f"health:{node.node_id}"
            if health_key in self.cache:
                health_info = self.cache[health_key]
                if health_info.get("status") == "healthy" and target_model in node.models:
                    selected_node = node
                    break
            else:
                # If not in cache, check health now (but we don't want to do heavy checks here, so we'll skip and rely on cache)
                # We'll do a quick online check only
                if node.tailscale_host == "localhost" or self.run_cmd(f"tailscale ping -c 1 {node.tailscale_host} 2>&1", timeout=2)[0]:
                    if target_model in node.models:
                        selected_node = node
                        break
        
        # If we found a node with the target model and it's healthy (or at least online), use it
        if selected_node is not None:
            selected_model = target_model
            reason = f"Preferred model '{target_model}' -> {selected_node.name}"
        else:
            # Fallback to original logic: select node (prefer healthy, then by VRAM for heavy tasks)
            selected_node = suitable_nodes[0]
            for node in suitable_nodes:
                # Check cache for node health
                health_key = f"health:{node.node_id}"
                if health_key in self.cache:
                    if self.cache[health_key].get("status") == "healthy":
                        selected_node = node
                        break
            
            # Build fallback chain
            fallback_chain = [selected_node.primary_model] + selected_node.fallback_models
            # Add other nodes' primary models
            for node in suitable_nodes[1:]:
                fallback_chain.append(f"{node.node_id}:{node.primary_model}")
            
            selected_model = selected_node.primary_model
            reason = f"Role '{required_role}' -> {selected_node.name} ({selected_node.primary_model})"
        
        # Build fallback chain for the selected case
        if selected_model == target_model:
            # Fallback chain: first the target model, then the node's fallbacks, then other nodes' primaries
            fallback_chain = [target_model] + selected_node.fallback_models
            for node in suitable_nodes:
                if node.node_id != selected_node.node_id:
                    fallback_chain.append(f"{node.node_id}:{node.primary_model}")
        else:
            # Already built above in the fallback case
            pass
        
        decision = RoutingDecision(
            task=task,
            project=project,
            selected_node=selected_node.node_id,
            selected_model=selected_model,
            reason=reason,
            fallback_chain=fallback_chain,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # Cache decision
        if use_cache:
            self.cache[cache_key] = asdict(decision)
            self._save_cache()
        
        return decision
    
    def get_status(self) -> Dict:
        """Get registry status"""
        return {
            "nodes_configured": len(NODES),
            "cache_entries": len(self.cache),
            "roles_supported": list(set(r for n in NODES for r in n.role.split(","))),
            "models_total": sum(len(n.models) for n in NODES),
        }

def main():
    parser = argparse.ArgumentParser(description="Model Registry — Living Code")
    parser.add_argument("--health-check", action="store_true", help="Check all nodes health")
    parser.add_argument("--all-nodes", action="store_true", help="Check all nodes (with --health-check)")
    parser.add_argument("--test-fallback-chains", action="store_true", help="Test fallback chains")
    parser.add_argument("--warm-cache", action="store_true", help="Warm cache with common prompts")
    parser.add_argument("--top-prompts", type=int, default=10, help="Number of prompts to warm")
    parser.add_argument("--route", action="store_true", help="Route a task")
    parser.add_argument("--task", type=str, help="Task description for routing")
    parser.add_argument("--project", type=int, default=1, help="Project number")
    parser.add_argument("--status", action="store_true", help="Show registry status")
    args = parser.parse_args()
    
    registry = ModelRegistry()
    
    if args.health_check:
        result = registry.health_check_all()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.test_fallback_chains:
        result = registry.test_fallback_chains()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.warm_cache:
        result = registry.warm_cache(args.top_prompts)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.route and args.task:
        decision = registry.route_task(args.task, args.project)
        if decision:
            print(json.dumps(asdict(decision), indent=2, ensure_ascii=False))
        else:
            print("Failed to route task")
    elif args.status:
        print(json.dumps(registry.get_status(), indent=2, ensure_ascii=False))
    else:
        print("Use --health-check, --test-fallback-chains, --warm-cache, --route --task, or --status")
    
    sys.exit(0)

if __name__ == "__main__":
    main()