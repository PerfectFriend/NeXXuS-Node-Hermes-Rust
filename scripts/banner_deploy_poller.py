#!/usr/bin/env python3
# Living Code Ecosystem — Banner Deploy Poller
# Версия: 1.0
# Опрашивает артефакты filter_overlord каждые 5 мин, запускает banner_deploy для READY компонентов
# Использование: python banner_deploy_poller.py --cycle 42 --poll-once | --daemon

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

class BannerDeployPoller:
    def __init__(self, cycle: int = None):
        self.root = Path("C:/LivingCode")
        self.artifacts_dir = self.root / "artifacts"
        # Auto-detect cycle if not provided
        if cycle is None:
            cycle = self._detect_latest_cycle()
        self.cycle = cycle
        self.processed_file = self.artifacts_dir / f"banner_poller_processed_cycle_{cycle:03d}.json"
        self.processed = self._load_processed()

    def _detect_latest_cycle(self) -> int:
        """Detect the latest cycle from filter report files."""
        import re
        report_files = list(self.artifacts_dir.glob("filter_report_cycle_*.json"))
        if not report_files:
            # Fallback: calculate cycle from time (4-hour cycles since epoch)
            # Using minutes since 2026-01-01 / 240 (4 hours)
            from datetime import datetime, timezone
            epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            cycle = int((now - epoch).total_seconds() / 240)
            print(f"  ������  No filter reports found, calculated cycle: {cycle}")
            return cycle
        
        # Extract cycle numbers from filenames
        cycles = []
        for f in report_files:
            match = re.search(r'filter_report_cycle_(\d+)\.json', f.name)
            if match:
                cycles.append(int(match.group(1)))
        
        if cycles:
            latest = max(cycles)
            print(f"  ��� Auto-detected latest cycle: {latest}")
            return latest
        
        # Fallback
        from datetime import datetime, timezone
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        cycle = int((now - epoch).total_seconds() / 240)
        print(f"  ������  Could not parse cycle from filenames, calculated: {cycle}")
        return cycle
    
    def _load_processed(self) -> set:
        if self.processed_file.exists():
            try:
                return set(json.loads(self.processed_file.read_text(encoding='utf-8')))
            except:
                return set()
        return set()
    
    def _save_processed(self):
        self.processed_file.write_text(json.dumps(list(self.processed), indent=2), encoding='utf-8')
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 120) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def check_for_ready(self) -> list:
        """Check filter reports for READY components"""
        ready_components = []
        
        # Look for filter reports for this cycle (supports both cycle_N and cycle_NNN formats)
        report_files = list(self.artifacts_dir.glob(f"filter_report_cycle_{self.cycle}.json"))
        if not report_files:
            report_files = list(self.artifacts_dir.glob(f"filter_report_cycle_{self.cycle:03d}.json"))
        
        for report_file in report_files:
            try:
                with open(report_file) as f:
                    report = json.load(f)
                
                for analysis in report.get("components", []):
                    if analysis.get("classification") == "READY":
                        component_key = analysis["name"]
                        if component_key not in self.processed:
                            ready_components.append({
                                "component": component_key,
                                "project": analysis["project"],
                                "reason": analysis.get("reason", ""),
                            })
            except:
                pass
        
        return ready_components
    
    def deploy_component(self, component: str, project: int) -> bool:
        """Run banner_deploy for component"""
        print(f"\n  🎨 Deploying banner for {component} (Project {project})...")
        
        success, out, err = self.run_cmd(
            f'python C:/LivingCode/scripts/banner_deploy.py --style brand --component "{component}" --cycle {self.cycle} --readme --langs ru,en,zh --create-repos',
            timeout=600
        )
        
        if success:
            print(f"     ✅ Banner deployed: {component}")
            self.processed.add(f"project{project}_{component}")
            self._save_processed()
            return True
        else:
            print(f"     ❌ Failed: {err[:200]}")
            return False
    
    def poll_once(self) -> int:
        """Single poll iteration"""
        print(f"\n🔍 BANNER POLLER — Cycle {self.cycle} — {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
        
        ready = self.check_for_ready()
        
        if not ready:
            print("  📭 No new READY components")
            return 0
        
        print(f"  📦 Found {len(ready)} READY component(s)")
        
        deployed = 0
        for item in ready:
            if self.deploy_component(item["component"], item["project"]):
                deployed += 1
        
        return deployed
    
    def run_daemon(self, interval: int = 300):
        """Run as daemon, polling every interval seconds"""
        print(f"\n{'='*60}")
        print(f"🎨 BANNER DEPLOY POLLER DAEMON — Cycle {self.cycle}")
        print(f"Poll interval: {interval}s (5 min)")
        print(f"{'='*60}")
        
        while True:
            try:
                self.poll_once()
            except KeyboardInterrupt:
                print("\n🛑 Poller stopped by user")
                break
            except Exception as e:
                print(f"  ❌ Poller error: {e}")
            
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Banner Deploy Poller")
    parser.add_argument("--cycle", type=int, default=None, help="Cycle number (auto-detected if not provided)")
    parser.add_argument("--poll-once", action="store_true", help="Single poll iteration")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval (seconds)")
    args = parser.parse_args()

    poller = BannerDeployPoller(args.cycle)
    
    if args.poll_once:
        poller.poll_once()
    elif args.daemon:
        poller.run_daemon(args.interval)
    else:
        # Default to single poll iteration for cron/agent compatibility
        poller.poll_once()
    
    sys.exit(0)


if __name__ == "__main__":
    main()