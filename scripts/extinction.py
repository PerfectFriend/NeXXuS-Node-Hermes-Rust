#!/usr/bin/env python3
# Living Code Ecosystem — Extinction Check (Daily 03:00)
# Версия: 1.0
# Узлы мёртвые >7 дней → экстинкция в archive/, запись в летопись
# Использование: python extinction.py --min-days 7

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List

class ExtinctionCheck:
    def __init__(self, min_days: int = 7):
        self.min_days = min_days
        self.root = Path("C:/Users/tomas/the-grimoire/ru")
        self.vault_root = Path("C:/Vault")
        self.pulse_history = self.vault_root / "Evolution" / "pulse-history.csv"
        self.evolution_dir = self.vault_root / "Evolution"
        self.archive_dir = self.evolution_dir / "archive"
        self.chronicle_path = self.vault_root / "Evolution" / "chronicle.md"
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 60) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.vault_root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def parse_pulse_history(self) -> Dict[str, int]:
        """Parse pulse-history.csv to get consecutive dead days per node"""
        if not self.pulse_history.exists():
            return {}
        
        content = self.pulse_history.read_text(encoding='utf-8')
        lines = content.strip().split('\n')
        
        if len(lines) < 2:
            return {}
        
        # Skip header
        dead_streaks = {}
        current_streaks = {}
        
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) >= 6:
                dead_nodes_str = parts[5].strip('"')
                dead_today = [n.strip() for n in dead_nodes_str.split(';') if n.strip()]
                
                # Update streaks
                all_nodes = set(current_streaks.keys()) | set(dead_today)
                
                for node in all_nodes:
                    if node in dead_today:
                        current_streaks[node] = current_streaks.get(node, 0) + 1
                    else:
                        # Node recovered, reset streak
                        if node in current_streaks:
                            dead_streaks[node] = max(dead_streaks.get(node, 0), current_streaks[node])
                        current_streaks[node] = 0
        
        # Final streaks
        for node, streak in current_streaks.items():
            dead_streaks[node] = max(dead_streaks.get(node, 0), streak)
        
        return dead_streaks
    
    def find_orphan_nodes(self) -> List[str]:
        """Find Evolution/*.md files without graph.yaml entry"""
        orphans = []
        
        # Load graph.yaml nodes
        graph_file = self.root / "configs" / "graph.yaml"
        graph_nodes = set()
        if graph_file.exists():
            import yaml
            with open(graph_file) as f:
                graph = yaml.safe_load(f)
            for node in graph.get("nodes", []):
                graph_nodes.add(node.get("id", ""))
        
        # Check Evolution folder
        for md_file in self.evolution_dir.glob("*.md"):
            if md_file.name in ["INDEX.md", "chronicle.md", "pulse-history.csv"]:
                continue
            node_id = md_file.stem
            if node_id not in graph_nodes and node_id not in ["Graph Dashboard", "Pulse History Dashboard", "Dead Nodes Dashboard"]:
                orphans.append(node_id)
        
        return orphans
    
    def extinct_node(self, node_id: str, reason: str) -> bool:
        """Move node to archive and record in chronicle"""
        source = self.evolution_dir / f"{node_id}.md"
        
        if not source.exists():
            print(f"  ⚠️  Node file not found: {source}")
            return False
        
        # Move to archive
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        dest = self.archive_dir / f"{node_id}.md"
        
        # Read content for archive
        content = source.read_text(encoding='utf-8')
        
        # Add extinction header
        archive_content = f"""---
extinct: true
extinction_date: {datetime.now(timezone.utc).isoformat()}
extinction_reason: {reason}
original_node: {node_id}
---

{content}
"""
        dest.write_text(archive_content, encoding='utf-8')
        
        # Remove original
        source.unlink()
        
        print(f"  🗂️  Archived: {node_id} -> {dest}")
        return True
    
    def update_chronicle(self, extinctions: List[Dict], orphans: List[str]):
        """Record extinctions in chronicle"""
        self.chronicle_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} — AUTO-EXTINCTION CHECK\n\n"
        entry += f"**Min days dead:** {self.min_days}\n\n"
        
        if extinctions:
            entry += "### Extinct Nodes (dead >7 days):\n"
            for ext in extinctions:
                entry += f"- **{ext['node']}**: {ext['reason']} (dead {ext['days']} days)\n"
        else:
            entry += "### Extinct Nodes: None\n"
        
        if orphans:
            entry += "\n### Orphan Nodes (not in graph.yaml):\n"
            for orphan in orphans:
                entry += f"- **{orphan}**: moved to archive\n"
        else:
            entry += "\n### Orphan Nodes: None\n"
        
        entry += "\n---\n"
        
        if self.chronicle_path.exists():
            content = self.chronicle_path.read_text(encoding='utf-8')
        else:
            content = "# Летопись Живого Кода\n\n"
        
        self.chronicle_path.write_text(content + entry, encoding='utf-8')
    
    def run(self) -> Dict:
        """Run extinction check"""
        print(f"\n{'='*60}")
        print(f"💀 EXTINCTION CHECK — Min days: {self.min_days}")
        print(f"{'='*60}")
        
        # Check pulse history
        print("  📊 Parsing pulse-history.csv...")
        dead_streaks = self.parse_pulse_history()
        
        if not dead_streaks:
            print("  ⚠️  Insufficient pulse history (need 7+ days)")
            return {"status": "insufficient_data", "extinctions": [], "orphans": []}
        
        print(f"  📈 Dead streaks: {dead_streaks}")
        
        # Find nodes to extinct
        extinctions = []
        for node, days in dead_streaks.items():
            if days >= self.min_days:
                extinctions.append({"node": node, "days": days, "reason": f"Dead for {days} consecutive days"})
        
        # Find orphans
        print("  🔍 Checking for orphan nodes...")
        orphans = self.find_orphan_nodes()
        
        # Process extinctions
        for ext in extinctions:
            print(f"\n  💀 Extincting: {ext['node']} (dead {ext['days']} days)")
            self.extinct_node(ext['node'], ext['reason'])
        
        # Process orphans
        for orphan in orphans:
            print(f"\n  🗂️  Archiving orphan: {orphan}")
            self.extinct_node(orphan, "Orphan node (not in graph.yaml)")
            extinctions.append({"node": orphan, "days": 0, "reason": "Orphan node"})
        
        # Update chronicle
        if extinctions or orphans:
            self.update_chronicle(extinctions, orphans)
            
            # Git commit
            self.run_cmd("git add Evolution/ Evolution/archive/ Evolution/chronicle.md", cwd=self.vault_root)
            self.run_cmd(f'git commit -m "extinction: {len(extinctions)} nodes archived"', cwd=self.vault_root)
        
        print(f"\n{'='*60}")
        if extinctions:
            print(f"✅ EXTINCTION COMPLETE: {len(extinctions)} nodes archived")
        else:
            print(f"✅ NO EXTINCTIONS NEEDED")
        print(f"{'='*60}")
        
        return {
            "status": "complete",
            "extinctions": extinctions,
            "orphans": orphans,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description="Extinction Check — Living Code")
    parser.add_argument("--min-days", type=int, default=7, help="Minimum consecutive dead days for extinction")
    args = parser.parse_args()
    
    extinction = ExtinctionCheck(args.min_days)
    result = extinction.run()
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    import json
    main()