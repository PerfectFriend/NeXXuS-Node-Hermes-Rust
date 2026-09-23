# HOT
#!/usr/bin/env python3
# Living Code Ecosystem — DJ Studio Poller
# Версия: 1.1
# Опрашивает артефакты filter_overlord для game компонентов, запускает dj_studio
# Использование: python dj_studio_poller.py [--cycle N] [--poll-once | --daemon]
# Cycle auto-detected from filter_report_cycle_XXX.json if omitted

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone


class DJStudioPoller:
    def __init__(self, cycle: int):
        self.cycle = cycle
        self.root = Path("/home/thomas/LivingCode")
        self.artifacts_dir = self.root / "artifacts"
        self.processed_file = self.artifacts_dir / f"dj_poller_processed_cycle_{cycle:03d}.json"
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

    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 300) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)

    def check_for_game_ready(self) -> list:
        """Check filter reports for READY game components"""
        game_components = []

        report_files = list(self.artifacts_dir.glob(f"filter_report_cycle_{self.cycle:03d}.json"))

        for report_file in report_files:
            try:
                with open(report_file) as f:
                    report = json.load(f)

                for analysis in report.get("analyses", []):
                    if analysis.get("classification") == "READY":
                        project = analysis.get("project", 0)
                        # Check if this is a game-related component
                        # In real implementation, would check component type from evolution summary
                        game_keywords = ["game", "engine", "renderer", "physics", "audio", "world", "level", "ui", "menu"]
                        component_name = f"project{project}_component"

                        # For now, treat all READY as potential game components
                        # In production, would read evolution summary to determine type
                        if component_name not in self.processed:
                            game_components.append({
                                "component": component_name,
                                "project": project,
                                "reason": analysis.get("reason", ""),
                            })
            except:
                pass

        return game_components

    def run_dj_studio(self, component: str, project: int) -> bool:
        """Run dj_studio for game component"""
        print(f"\n  ��� Running DJ Studio for {component} (Project {project})...")

        success, out, err = self.run_cmd(
            f'python dj_studio.py --component "{component}" --cycle {self.cycle} '
            f'--sound-design --adaptive-music --spatial '
            f'--middleware fmod,wwise --engines unity,godot,unreal --formats ambisonics,binaural',
            timeout=600
        )

        if success:
            print(f"     �� DJ Studio complete: {component}")
            self.processed.add(component)
            self._save_processed()
            return True
        else:
            print(f"     ��� Failed: {err[:200]}")
            return False

    def poll_once(self) -> int:
        """Single poll iteration"""
        print(f"\n���� DJ STUDIO POLLER — Cycle {self.cycle} — {datetime.now(timezone.utc).strftime('%H:%M:%S')}")

        ready = self.check_for_game_ready()

        if not ready:
            print("  ��� No new READY game components")
            return 0

        print(f"  ��� Found {len(ready)} READY game component(s)")

        deployed = 0
        for item in ready:
            if self.run_dj_studio(item["component"], item["project"]):
                deployed += 1

        return deployed

    def run_daemon(self, interval: int = 300):
        """Run as daemon"""
        print(f"\n{'='*60}")
        print(f"���� DJ STUDIO POLLER DAEMON — Cycle {self.cycle}")
        print(f"Poll interval: {interval}s")
        print(f"{'='*60}")

        while True:
            try:
                self.poll_once()
            except KeyboardInterrupt:
                print("\n���� Poller stopped")
                break
            except Exception as e:
                print(f"  ��� Error: {e}")

            time.sleep(interval)


def auto_detect_cycle() -> int:
    """Auto-detect the current active cycle from professor_sync or cycle_start files."""
    root = Path("/home/thomas/LivingCode")
    artifacts_dir = root / "artifacts"
    
    # First priority: professor_sync_cycle_XXX.json (current active cycle)
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("professor_sync_cycle_*.json"):
            match = re.search(r"cycle_(\d+)\.json$", f.name)
            if match:
                try:
                    with open(f) as fp:
                        data = json.load(fp)
                    if "cycle" in data:
                        return data["cycle"]
                except:
                    pass
    
    # Second priority: cycle_start_XXX.json
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("cycle_start_*.json"):
            match = re.search(r"cycle_start_(\d+)\.json$", f.name)
            if match:
                try:
                    with open(f) as fp:
                        data = json.load(fp)
                    if "cycle" in data:
                        return data["cycle"]
                except:
                    pass
    
    # Third priority: filter reports (latest cycle with data)
    cycles = set()
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("filter_report_cycle_*.json"):
            match = re.search(r"cycle_(\d+)\.json$", f.name)
            if match:
                cycles.add(int(match.group(1)))
    
    if cycles:
        return max(cycles)
    
    # Fallback: any cycle_XXX pattern
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("*cycle_*.json"):
            match = re.search(r"cycle_(\d+)\.json$", f.name)
            if match:
                cycles.add(int(match.group(1)))
    
    if cycles:
        return max(cycles)
    
    return None


def main():
    parser = argparse.ArgumentParser(description="DJ Studio Poller")
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
            print("��� Could not auto-detect cycle. Please specify --cycle N")
            sys.exit(1)
        print(f"���� Auto-detected cycle: {cycle}")

    poller = DJStudioPoller(cycle)

    # Default to --poll-once if neither specified
    if args.daemon:
        poller.run_daemon(args.interval)
    else:
        poller.poll_once()

    sys.exit(0)


if __name__ == "__main__":
    main()