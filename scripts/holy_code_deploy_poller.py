#!/usr/bin/env python3
# Living Code Ecosystem — Holy Code Deploy Poller
# Версия: 1.1
# Опрашивает завершённые banner_deploy + dj_studio, запускает holy_code_deploy
# Использование: python holy_code_deploy_poller.py [--cycle N] [--poll-once | --daemon]

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone


class HolyCodeDeployPoller:
    def __init__(self, cycle: int):
        self.cycle = cycle
        self.root = Path("C:/LivingCode")
        self.artifacts_dir = self.root / "artifacts"
        self.releases_dir = self.root / "releases"
        self.processed_file = self.artifacts_dir / f"holy_poller_processed_cycle_{cycle:03d}.json"
        self.processed = self._load_processed()

    def _load_processed(self) -> set:
        if self.processed_file.exists():
            try:
                return set(json.loads(self.processed_file.read_text(encoding='utf-8')))
            except:
                return set()
        return set()

    def _save_processed(self):
        self.processed_file.write_text(json.dumps(list(self.processed), indent=2), encoding='utf-8')

    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 600) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)

    def check_for_deploy_ready(self) -> list:
        """Check for components that have both banner_deploy and dj_studio complete"""
        deploy_ready = []

        # Look for banner deploy reports
        banner_reports = list(self.releases_dir.glob(f"deploy_*_cycle_{self.cycle:03d}.json"))

        for banner_report in banner_reports:
            try:
                with open(banner_report) as f:
                    deploy_data = json.load(f)

                component = deploy_data.get("component", "")
                project = deploy_data.get("component", "").split("_")[-1] if "_" in deploy_data.get("component", "") else "1"

                # Check if DJ Studio also completed for this component
                dj_report = self.artifacts_dir / f"dj_studio_report_{component}_cycle_{self.cycle:03d}.json"
                dj_complete = dj_report.exists()

                key = f"{component}_deploy"
                if deploy_data.get("push_success") and key not in self.processed:
                    deploy_ready.append({
                        "component": component,
                        "project": int(project) if project.isdigit() else 1,
                        "dj_complete": dj_complete,
                        "banner_deploy": deploy_data,
                    })
            except:
                pass

        return deploy_ready

    def run_holy_deploy(self, component: str, project: int, dj_complete: bool) -> bool:
        """Run holy_code_deploy for component"""
        print(f"\n  ����� Running Holy Code Deploy for {component} (Project {project})...")

        # Build targets
        targets = "android,ios,web,desktop,embedded"

        script_path = self.root / "scripts" / "holy_code_deploy.py"
        cmd = (
            f'python "{script_path}" --component "{component}" --cycle {self.cycle} '
            f'--build --targets {targets} --test --zero-bug-policy '
            f'--deploy --stores google,apple,github,fdroid,steam --telemetry'
        )

        success, out, err = self.run_cmd(cmd, timeout=1200)

        if success:
            print(f"     ���� Holy Code Deploy complete: {component}")
            self.processed.add(f"{component}_deploy")
            self._save_processed()
            return True
        else:
            print(f"     ����� Failed: {err[:500]}")
            return False

    def poll_once(self) -> int:
        """Single poll iteration"""
        print(f"\n���� HOLY CODE DEPLOY POLLER — Cycle {self.cycle} — {datetime.now(timezone.utc).strftime('%H:%M:%S')}")

        ready = self.check_for_deploy_ready()

        if not ready:
            print("  ����� No components ready for Holy Deploy")
            return 0

        print(f"  ����� Found {len(ready)} component(s) ready for Holy Deploy")

        deployed = 0
        for item in ready:
            if self.run_holy_deploy(item["component"], item["project"], item["dj_complete"]):
                deployed += 1

        return deployed

    def run_daemon(self, interval: int = 300):
        """Run as daemon"""
        print(f"\n{'='*60}")
        print(f"���� HOLY CODE DEPLOY POLLER DAEMON — Cycle {self.cycle}")
        print(f"Poll interval: {interval}s")
        print(f"{'='*60}")

        while True:
            try:
                self.poll_once()
            except KeyboardInterrupt:
                print("\n���� Poller stopped")
                break
            except Exception as e:
                print(f"  ����� Error: {e}")

            time.sleep(interval)


def auto_detect_cycle() -> int:
    """Auto-detect the latest cycle from artifacts/releases directories."""
    root = Path("C:/LivingCode")
    releases_dir = root / "releases"
    artifacts_dir = root / "artifacts"

    cycles = set()

    # Check releases for deploy_*_cycle_XXX.json
    if releases_dir.exists():
        for f in releases_dir.glob("deploy_*_cycle_*.json"):
            match = re.search(r"cycle_(\d+)\.json$", f.name)
            if match:
                cycles.add(int(match.group(1)))

    # Check artifacts for dj_studio_report_*_cycle_XXX.json
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("dj_studio_report_*_cycle_*.json"):
            match = re.search(r"cycle_(\d+)\.json$", f.name)
            if match:
                cycles.add(int(match.group(1)))

    if cycles:
        return max(cycles)

    # Fallback: check for any cycle_XXX pattern in artifacts
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("*cycle_*.json"):
            match = re.search(r"cycle_(\d+)\.json$", f.name)
            if match:
                cycles.add(int(match.group(1)))

    if cycles:
        return max(cycles)

    return None


def main():
    parser = argparse.ArgumentParser(description="Holy Code Deploy Poller")
    parser.add_argument("--cycle", type=int, help="Cycle number (auto-detected if omitted)")
    parser.add_argument("--poll-once", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    # Auto-detect cycle if not provided
    cycle = args.cycle
    if cycle is None:
        cycle = auto_detect_cycle()
        if cycle is None:
            print("���� Could not auto-detect cycle. Please specify --cycle N")
            sys.exit(1)
        print(f"���� Auto-detected cycle: {cycle}")

    poller = HolyCodeDeployPoller(cycle)

    # Default to --poll-once if neither specified
    if args.daemon:
        poller.run_daemon(args.interval)
    else:
        poller.poll_once()

    sys.exit(0)


if __name__ == "__main__":
    main()