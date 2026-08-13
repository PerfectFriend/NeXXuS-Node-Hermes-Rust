#!/usr/bin/env python3
# Living Code Ecosystem — Model Registry Health (Every 30 min)
# Версия: 1.0
# Проверка доступности всех моделей на всех 6 узлах Tailscale
# Использование: python model_registry_health.py --health-check --all-nodes --test-fallback-chains --warm-cache --top-10-prompts

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict

class ModelRegistryHealth:
    def __init__(self):
        self.root = Path("C:/LivingCode")
        self.scripts_dir = Path("C:/Users/tomas/the-grimoire/ru/scripts")
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 60) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def run_model_registry(self, args: str) -> Dict:
        """Run model_registry.py with given args"""
        hermes_python = r"C:\Users\tomas\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
        
        cmd = f'"{hermes_python}" model_registry.py {args}'
        success, out, err = self.run_cmd(cmd, cwd=self.scripts_dir, timeout=120)
        
        try:
            return json.loads(out) if out.strip() else {"success": success, "output": out, "error": err}
        except:
            return {"success": success, "output": out, "error": err}
    
    def health_check_all(self) -> Dict:
        """Run health check on all nodes"""
        print(f"\n🤖 MODEL REGISTRY HEALTH CHECK — {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
        result = self.run_model_registry("--health-check --all-nodes")
        
        if "nodes" in result:
            healthy = result.get("healthy_nodes", 0)
            total = result.get("total_nodes", 6)
            print(f"  📊 {healthy}/{total} nodes healthy")
            
            for node in result.get("nodes", []):
                icon = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}.get(node.get("status", ""), "❓")
                print(f"     {icon} {node.get('name', 'Unknown')}: {node.get('status', 'unknown')} ({node.get('latency_ms', 0)}ms)")
        
        return result
    
    def test_fallback_chains(self) -> Dict:
        """Test fallback chains"""
        print(f"\n🔄 TESTING FALLBACK CHAINS")
        result = self.run_model_registry("--test-fallback-chains")
        
        if "fallback_tests" in result:
            for test in result["fallback_tests"]:
                status = "✅" if test.get("chain_ok") else "❌"
                print(f"  {status} {test.get('node', 'unknown')}: chain_ok={test.get('chain_ok')}")
        
        return result
    
    def warm_cache(self, top_prompts: int = 10) -> Dict:
        """Warm cache with common prompts"""
        print(f"\n🔥 WARMING CACHE ({top_prompts} prompts)")
        result = self.run_model_registry(f"--warm-cache --top-prompts {top_prompts}")
        
        print(f"  📦 Warmed: {result.get('warmed', 0)} | Cache size: {result.get('cache_size', 0)}")
        
        return result
    
    def run_full_check(self) -> Dict:
        """Run complete health check"""
        print(f"\n{'='*60}")
        print(f"🤖 MODEL REGISTRY HEALTH — FULL CHECK")
        print(f"{'='*60}")
        
        results = {}
        
        results["health"] = self.health_check_all()
        results["fallback"] = self.test_fallback_chains()
        results["cache"] = self.warm_cache(10)
        
        # Alert if unhealthy
        health = results.get("health", {})
        if health.get("healthy_nodes", 0) < health.get("total_nodes", 6):
            print(f"\n⚠️  ALERT: Some nodes unhealthy!")
            # Would alert filter_overlord in real implementation
        
        print(f"\n{'='*60}")
        print(f"✅ HEALTH CHECK COMPLETE")
        print(f"{'='*60}")
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Model Registry Health Check")
    parser.add_argument("--health-check", action="store_true")
    parser.add_argument("--all-nodes", action="store_true")
    parser.add_argument("--test-fallback-chains", action="store_true")
    parser.add_argument("--warm-cache", action="store_true")
    parser.add_argument("--top-prompts", type=int, default=10)
    args = parser.parse_args()
    
    health = ModelRegistryHealth()
    
    if args.health_check and args.all_nodes:
        health.health_check_all()
    elif args.test_fallback_chains:
        health.test_fallback_chains()
    elif args.warm_cache:
        health.warm_cache(args.top_prompts)
    else:
        # Default: run full check
        health.run_full_check()
    
    sys.exit(0)


if __name__ == "__main__":
    main()