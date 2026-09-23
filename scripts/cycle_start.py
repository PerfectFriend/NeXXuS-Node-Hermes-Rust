# HOT
#!/usr/bin/env python3
# Living Code Ecosystem — Cycle Start (T+0min) — Linux version
# Git pull, health checks, chronicle entry, encrypted_comm briefing, promotion check
# Usage: python cycle_start.py --cycle 42

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict

class CycleStart:
    def __init__(self, cycle: int):
        self.cycle = cycle
        self.root = Path("/home/thomas/LivingCode")
        self.vault_root = Path("/home/thomas/Documents/ObsidianVault")
        self.grimoire_root = Path("/home/thomas/the-grimoire/ru")
        self.chronicle_path = self.vault_root / "Evolution" / "chronicle.md"
   
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 120) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
   
    def git_pull_all(self) -> Dict:
        """Git pull --rebase on all repos"""
        print("  📥 Git pull --rebase all repos...")
        repos = [
            ("LivingCode Root", self.root),
            ("Vault", self.vault_root),
            ("Grimoire", self.grimoire_root),
        ]
        # Add active projects
        queue_file = self.root / "QUEUE.json"
        if queue_file.exists():
            q = json.loads(queue_file.read_text())
            for project in q.get("active", []):
                repos.append((project, self.root / "Projects" / project))
        
        results = []
        for name, path in repos:
            if path.exists():
                success, out, err = self.run_cmd("git pull --rebase", cwd=path, timeout=60)
                results.append({"repo": name, "success": success, "output": out[:200] if out else err[:200]})
                status = "✅" if success else "⚠️"
                print(f"     {status} {name}")
            else:
                results.append({"repo": name, "success": False, "output": "Path not found"})
                print(f"     ❌ {name}: not found")
       
        return {"repos": results, "all_ok": all(r["success"] for r in results)}
   
    def check_tailscale_mesh(self) -> Dict:
        """Check Tailscale connectivity"""
        print("  🔗 Checking Tailscale mesh...")
        nodes = ["lenovo", "dell", "totomoto", "unsloth-studio", "ubuntu-server"]
        results = []
       
        for node in nodes:
            success, out, err = self.run_cmd(f"tailscale ping -c 1 {node} 2>&1", timeout=10)
            online = success and "pong" in out.lower()
            results.append({"node": node, "online": online})
            icon = "✅" if online else "❌"
            print(f"     {icon} {node}: {'online' if online else 'offline'}")
       
        return {"nodes": results, "all_online": all(r["online"] for r in results)}
   
    def check_model_registry(self) -> Dict:
        """Quick model registry health check"""
        print("  🤖 Checking model registry...")
        script = self.grimoire_root / "scripts" / "model_registry.py"
       
        success, out, err = self.run_cmd(f'python "{script}" --health-check --all-nodes', cwd=self.grimoire_root, timeout=60)
       
        try:
            result = json.loads(out) if out.strip() else {"success": success}
        except:
            result = {"success": success, "output": out}
       
        if "healthy_nodes" in result:
            print(f"     📊 {result.get('healthy_nodes', 0)}/{result.get('total_nodes', 6)} nodes healthy")
       
        return result
   
    def run_promotion_check(self) -> Dict:
        """Run promotion check at cycle start"""
        print("  🔄 Running promotion check...")
        success, out, err = self.run_cmd("python /home/thomas/LivingCode/scripts/promote_check.py", timeout=60)
        return {"success": success, "output": out[:200] if out else err[:200]}
   
    def update_chronicle(self) -> bool:
        """Add CYCLE_START entry to chronicle"""
        self.chronicle_path.parent.mkdir(parents=True, exist_ok=True)
       
        entry = f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} — CYCLE START {self.cycle}/120\n\n"
        entry += f"**Cycle:** {self.cycle}/120\n"
        entry += f"**Started:** {datetime.now(timezone.utc).isoformat()}\n"
        entry += f"**Duration:** 4 hours\n\n"
        entry += "---\n"
       
        if self.chronicle_path.exists():
            content = self.chronicle_path.read_text(encoding='utf-8')
        else:
            content = "# Летопись Живого Кода\n\n"
       
        self.chronicle_path.write_text(content + entry, encoding='utf-8')
        print("  📜 Chronicle updated")
        return True
   
    def send_briefing(self) -> Dict:
        """Trigger encrypted_comm briefing"""
        print("  📢 Sending cycle briefing via encrypted_comm...")
        script = Path("/home/thomas/.hermes/scripts/encrypted_comm.py")
        
        success, out, err = self.run_cmd(f'python "{script}" --briefing --cycle {self.cycle}', timeout=30)
        
        return {"success": success, "output": out[:200] if out else err[:200]}
   
    def run(self) -> Dict:
        """Run complete cycle start sequence"""
        print(f"\n{'='*60}")
        print(f"🚀 CYCLE START — Cycle {self.cycle}/120")
        print(f"{'='*60}")
       
        results = {}
       
        # Phase 0: Promotion check (NEW)
        results["promotion"] = self.run_promotion_check()
       
        # Phase 1: Git sync
        results["git_sync"] = self.git_pull_all()
       
        # Phase 2: Tailscale mesh
        results["tailscale"] = self.check_tailscale_mesh()
       
        # Phase 3: Model registry
        results["model_registry"] = self.check_model_registry()
       
        # Phase 4: Chronicle
        results["chronicle"] = self.update_chronicle()
       
        # Phase 5: Briefing
        results["briefing"] = self.send_briefing()
       
        # Overall status
        all_ok = (
            results["git_sync"].get("all_ok", False) and
            results["tailscale"].get("all_online", False) and
            results["model_registry"].get("success", False)
        )
       
        results["overall_success"] = all_ok
        results["cycle"] = self.cycle
        results["timestamp"] = datetime.now(timezone.utc).isoformat()
       
        print(f"\n{'='*60}")
        if all_ok:
            print(f"✅ CYCLE {self.cycle} START SUCCESSFUL")
        else:
            print(f"⚠️  CYCLE {self.cycle} START HAS WARNINGS")
        print(f"{'='*60}")
       
        return results


def auto_detect_cycle() -> int:
    """Auto-detect the current cycle based on 4-hour intervals since 2026-01-01."""
    from datetime import datetime, timezone
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    cycle = int((now - epoch).total_seconds() / 14400)  # 4 hours = 14400 seconds
    return cycle

def main():
    parser = argparse.ArgumentParser(description="Cycle Start — Living Code")
    parser.add_argument("--cycle", type=int, help="Cycle number (auto-detected if omitted)")
    args = parser.parse_args()
   
    # Auto-detect cycle if not provided
    cycle = args.cycle
    if cycle is None:
        cycle = auto_detect_cycle()
        print(f"🔄 Auto-detected cycle: {cycle}")
   
    starter = CycleStart(cycle)
    result = starter.run()
   
    # Save report
    report_file = Path("/home/thomas/LivingCode/artifacts") / f"cycle_start_{cycle:03d}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
   
    sys.exit(0 if result.get("overall_success") else 1)


if __name__ == "__main__":
    import json
    main()