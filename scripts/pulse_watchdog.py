#!/usr/bin/env python3
# Living Code Ecosystem — Pulse Watchdog (Hourly Health Check)
# Версия: 1.0
# Запускает pulse.py --quiet каждый час, алертит если есть мёртвые узлы
# Использование: python pulse_watchdog.py --cycle-aware | --silent-unless-sick

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

class PulseWatchdog:
    def __init__(self, cycle_aware: bool = False, silent_unless_sick: bool = False):
        self.cycle_aware = cycle_aware
        self.silent_unless_sick = silent_unless_sick
        self.root = Path("C:/Users/tomas/the-grimoire/ru")
        self.scripts_dir = self.root / "scripts"
        self.vault_root = Path("C:/Vault")
        self.pulse_history = self.vault_root / "Evolution" / "pulse-history.csv"
        self.pulse_history.parent.mkdir(parents=True, exist_ok=True)
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 60) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.scripts_dir)
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)
    
    def run_pulse(self) -> Dict:
        """Run pulse.py --quiet and parse output"""
        # Use the hermes python environment
        hermes_python = r"C:\Users\tomas\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
        
        code, out, err = self.run_cmd(f'"{hermes_python}" pulse.py --quiet')
        
        dead_nodes = []
        if "МЁРТВЫЕ:" in out:
            # Parse: [timestamp] PULSE: МЁРТВЫЕ: node1, node2, ...
            import re
            match = re.search(r'МЁРТВЫЕ:\s*(.+)', out)
            if match:
                dead_str = match.group(1).strip()
                if dead_str:
                    dead_nodes = [n.strip() for n in dead_str.split(',')]
        
        return {
            "exit_code": code,
            "dead_nodes": dead_nodes,
            "raw_output": out.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def log_pulse_history(self, pulse_result: Dict):
        """Append to pulse-history.csv"""
        dead_nodes = pulse_result["dead_nodes"]
        timestamp = datetime.now(timezone.utc)
        
        # Ensure CSV header
        if not self.pulse_history.exists():
            self.pulse_history.write_text("date,time,total_nodes,alive_nodes,dead_count,dead_nodes\n", encoding='utf-8')
        
        # We don't know total/alive from --quiet, so estimate
        total_nodes = 35  # from graph.yaml
        dead_count = len(dead_nodes)
        alive_nodes = total_nodes - dead_count
        
        line = f"{timestamp.date()},{timestamp.time()},{total_nodes},{alive_nodes},{dead_count},\"{';'.join(dead_nodes)}\"\n"
        
        with open(self.pulse_history, 'a', encoding='utf-8') as f:
            f.write(line)
    
    def run_watchdog(self) -> Dict:
        """Run godmode-watchdog.py"""
        hermes_python = r"C:\Users\tomas\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
        
        code, out, err = self.run_cmd(f'"{hermes_python}" godmode-watchdog.py')
        
        return {
            "exit_code": code,
            "output": out.strip(),
            "errors": err.strip()
        }
    
    def git_commit_pulse(self) -> bool:
        """Git commit pulse-history.csv"""
        code, out, err = self.run_cmd("git add Evolution/pulse-history.csv && git commit -m 'pulse: hourly check'", cwd=self.vault_root)
        return code == 0
    
    def check_dead_nodes(self, dead_nodes: list):
        """Alert if dead nodes found"""
        if not dead_nodes:
            if not self.silent_unless_sick:
                print("  ✅ All nodes healthy")
            return
        
        print(f"  ⚠️  DEAD NODES DETECTED: {', '.join(dead_nodes)}")
        
        # In real implementation, would send Telegram alert to Oracle + Gardener
        # For now, just log
        alert_file = self.root / "logs" / f"pulse_alert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        alert_file.parent.mkdir(parents=True, exist_ok=True)
        alert_file.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dead_nodes": dead_nodes,
            "alerted": True
        }, indent=2), encoding='utf-8')
    
    def run(self) -> Dict:
        """Run complete watchdog cycle"""
        if not self.silent_unless_sick:
            print(f"\n💓 PULSE WATCHDOG — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Run pulse
        pulse_result = self.run_pulse()
        
        if not self.silent_unless_sick or pulse_result["dead_nodes"]:
            print(f"  Pulse: {pulse_result['raw_output']}")
        
        # Log to CSV
        self.log_pulse_history(pulse_result)
        
        # Check dead nodes
        self.check_dead_nodes(pulse_result["dead_nodes"])
        
        # Run watchdog script
        watchdog_result = self.run_watchdog()
        
        # Git commit
        committed = self.git_commit_pulse()
        if committed and not self.silent_unless_sick:
            print("  💾 Pulse history committed to git")
        
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pulse": pulse_result,
            "watchdog": watchdog_result,
            "git_committed": committed
        }
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Pulse Watchdog — Living Code")
    parser.add_argument("--cycle-aware", action="store_true", help="Include cycle info")
    parser.add_argument("--silent-unless-sick", action="store_true", help="Only output if dead nodes found")
    args = parser.parse_args()
    
    watchdog = PulseWatchdog(args.cycle_aware, args.silent_unless_sick)
    result = watchdog.run()
    
    # Exit code: 0 if all healthy, 1 if dead nodes
    sys.exit(1 if result["pulse"]["dead_nodes"] else 0)


if __name__ == "__main__":
    main()