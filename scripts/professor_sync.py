#!/usr/bin/env python3
# Living Code Ecosystem — Professor Sync
# Версия: 1.0
# Синхронизация памяти Профессора → 4 проекта (каждые 4 часа)
# Использование: python professor_sync.py --project 1 --cycle 42 | --all --cycle 42

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

@dataclass
class Insight:
    topic: str
    category: str
    summary: str
    source_url: str
    source_type: str  # x.com, github, hn, blog, arxiv
    relevance_score: float  # 0.0-1.0
    applicable_projects: List[int]
    tags: List[str]
    timestamp: str

class ProfessorSync:
    def __init__(self, cycle: int):
        self.cycle = cycle
        self.root = Path("/home/thomas/LivingCode")
        self.vault_root = Path("/home/thomas/Documents/ObsidianVault")
        self.textbook_path = self.vault_root / "Учебник.md"
        self.chronicle_path = self.vault_root / "Evolution" / "chronicle.md"
        self.ai_eng_daily_dir = self.vault_root / "Evolution" / "AI-Engineering-Daily"
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 60) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def load_textbook_insights(self) -> List[Insight]:
        """Load latest insights from Учебник.md and AI-Engineering-Daily"""
        insights = []
        
        # Load from AI-Engineering-Daily (most recent)
        if self.ai_eng_daily_dir.exists():
            daily_files = sorted(self.ai_eng_daily_dir.glob("*.md"), reverse=True)
            for daily_file in daily_files[:3]:  # Last 3 daily notes
                try:
                    content = daily_file.read_text(encoding='utf-8')
                    # Parse insights from daily note
                    lines = content.split('\n')
                    current_insight = {}
                    for line in lines:
                        if line.startswith('## ') and 'Insight' in line:
                            if current_insight:
                                insights.append(self._create_insight(current_insight))
                            current_insight = {"category": "AI Engineering", "source_type": "ai_eng_daily"}
                        elif line.startswith('- **') and 'Source:' in line:
                            # Extract source
                            import re
                            m = re.search(r'Source:\s*@?(\S+)', line)
                            if m:
                                current_insight["source_url"] = m.group(1)
                                current_insight["source_type"] = "x.com" if "x.com" in line or "@" in line else "web"
                        elif line.startswith('  - ') and current_insight:
                            current_insight.setdefault("summary", "")
                            current_insight["summary"] += line.strip() + " "
                    if current_insight:
                        insights.append(self._create_insight(current_insight))
                except:
                    pass
        
        # Load from Учебник.md (learned topics)
        if self.textbook_path.exists():
            content = self.textbook_path.read_text(encoding='utf-8')
            # Find 🟢 topics (learned)
            for line in content.split('\n'):
                if '🟢' in line and '[' in line:
                    import re
                    m = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
                    if m:
                        insights.append(Insight(
                            topic=m.group(1),
                            category="Textbook",
                            summary=f"Learned topic from Учебник: {m.group(1)}",
                            source_url=m.group(2),
                            source_type="textbook",
                            relevance_score=0.9,
                            applicable_projects=[1,2,3,4],
                            tags=["learned", "textbook"],
                            timestamp=datetime.now(timezone.utc).isoformat()
                        ))
        
        return insights
    
    def _create_insight(self, data: Dict) -> Insight:
        return Insight(
            topic=data.get("topic", "Unknown"),
            category=data.get("category", "General"),
            summary=data.get("summary", "")[:500],
            source_url=data.get("source_url", ""),
            source_type=data.get("source_type", "web"),
            relevance_score=data.get("relevance_score", 0.7),
            applicable_projects=data.get("applicable_projects", [1,2,3,4]),
            tags=data.get("tags", []),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def sync_to_project(self, project: int, insights: List[Insight]) -> Dict:
        """Sync relevant insights to project memory"""
        project_root = self.root / f"Project{project}"
        memory_dir = project_root / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Filter insights for this project
        relevant = [i for i in insights if project in i.applicable_projects]
        
        if not relevant:
            return {"project": project, "synced": 0, "message": "No relevant insights"}
        
        # Create/update memory file
        memory_file = memory_dir / f"professor_insights_cycle_{self.cycle:03d}.json"
        memory_data = {
            "cycle": self.cycle,
            "project": project,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "insights": [asdict(i) for i in relevant],
            "total_insights": len(relevant)
        }
        
        memory_file.write_text(json.dumps(memory_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # Also append to project's CHRONICLE.md
        chronicle_file = project_root / "CHRONICLE.md"
        entry = f"\n## Cycle {self.cycle} — Professor Sync ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})\n\n"
        for insight in relevant:
            entry += f"- **{insight.topic}** ({insight.category}) — {insight.summary[:100]}... [Source: {insight.source_url}]\n"
        entry += "\n---\n"
        
        if chronicle_file.exists():
            content = chronicle_file.read_text(encoding='utf-8')
        else:
            content = f"# Project {project} Chronicle\n\n"
        chronicle_file.write_text(content + entry, encoding='utf-8')
        
        # Git commit
        self.run_cmd("git add -A", cwd=project_root)
        self.run_cmd(f'git commit -m "professor_sync: cycle {self.cycle} - {len(relevant)} insights synced"', cwd=project_root)
        
        return {"project": project, "synced": len(relevant), "memory_file": str(memory_file)}
    
    def sync_all(self) -> Dict:
        """Sync to all 4 projects"""
        print(f"\n{'='*60}")
        print(f"👨‍🏫 PROFESSOR SYNC — Cycle {self.cycle}")
        print(f"{'='*60}")
        
        insights = self.load_textbook_insights()
        print(f"  📚 Loaded {len(insights)} insights from textbook + AI-Eng-Daily")
        
        results = []
        for project in [1, 2, 3, 4]:
            print(f"\n  🔄 Syncing to Project {project}...")
            result = self.sync_to_project(project, insights)
            results.append(result)
            print(f"     ✅ Synced {result['synced']} insights")
        
        # Update main chronicle
        self.update_main_chronicle(insights)
        
        summary = {
            "cycle": self.cycle,
            "total_insights": len(insights),
            "projects": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        report_file = (self.root / "artifacts") / f"professor_sync_cycle_{self.cycle:03d}.json"
        (self.root / "artifacts").mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print(f"\n{'='*60}")
        print(f"✅ PROFESSOR SYNC COMPLETE: {sum(r['synced'] for r in results)} total insights synced")
        print(f"Report: {report_file}")
        print(f"{'='*60}")
        
        return summary
    
    def update_main_chronicle(self, insights: List[Insight]):
        """Update main vault chronicle"""
        self.chronicle_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} — Professor Sync (Cycle {self.cycle})\n\n"
        entry += f"**Insights loaded:** {len(insights)}\n\n"
        
        for insight in insights[:10]:  # Top 10
            entry += f"- **{insight.topic}** ({insight.category}, {insight.relevance_score:.0%}) — {insight.summary[:120]}...\n"
        
        if len(insights) > 10:
            entry += f"- ... and {len(insights) - 10} more\n"
        
        entry += "\n---\n"
        
        if self.chronicle_path.exists():
            content = self.chronicle_path.read_text(encoding='utf-8')
        else:
            content = "# Летопись Живого Кода\n\n"
        
        self.chronicle_path.write_text(content + entry, encoding='utf-8')


def auto_detect_cycle() -> int:
    """Auto-detect the current cycle based on 4-hour intervals since 2026-01-01."""
    from datetime import datetime, timezone
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    cycle = int((now - epoch).total_seconds() / 14400)  # 4 hours = 14400 seconds
    return cycle

def main():
    parser = argparse.ArgumentParser(description="Professor Sync — Living Code")
    parser.add_argument("--project", type=int, choices=[1,2,3,4], help="Specific project")
    parser.add_argument("--all", action="store_true", help="Sync to all 4 projects")
    parser.add_argument("--cycle", type=int, help="Cycle number (auto-detected if omitted)")
    args = parser.parse_args()
    
    # Auto-detect cycle if not provided
    cycle = args.cycle
    if cycle is None:
        cycle = auto_detect_cycle()
        print(f"����‍���� Auto-detected cycle: {cycle}")
    
    sync = ProfessorSync(cycle)
    
    if args.all:
        sync.sync_all()
    elif args.project:
        insights = sync.load_textbook_insights()
        sync.sync_to_project(args.project, insights)
    else:
        print("Use --all or --project <1-4>")
    
    sys.exit(0)


if __name__ == "__main__":
    main()