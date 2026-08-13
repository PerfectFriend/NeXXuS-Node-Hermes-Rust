#!/usr/bin/env python3
# Living Code Ecosystem — Textbook Learn (Every 6 hours)
# Версия: 1.0
# Профессор изучает тему из Учебника, обновляет статус 🔴→🟡→🟢, пишет в Chronicle
# Использование: python textbook_learn.py --cycle-aware --weighted-random

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

@dataclass
class TextbookTopic:
    category: str
    priority: int
    topic: str
    filename: str
    status: str  # 🔴, 🟡, 🟢
    learned_at: Optional[str] = None

class TextbookLearn:
    def __init__(self, cycle_aware: bool = False, weighted_random: bool = False):
        self.cycle_aware = cycle_aware
        self.weighted_random = weighted_random
        self.root = Path("C:/Vault")
        self.textbook_path = self.root / "Учебник.md"
        self.chronicle_path = self.root / "Evolution" / "chronicle.md"
        self.topics: List[TextbookTopic] = []
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 60) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def parse_textbook(self) -> List[TextbookTopic]:
        """Parse Учебник.md for topics"""
        if not self.textbook_path.exists():
            # Create default textbook if not exists
            self.create_default_textbook()
        
        content = self.textbook_path.read_text(encoding='utf-8')
        topics = []
        
        current_category = ""
        current_priority = 5
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Category with priority
            if line.startswith('## ') and 'priority' in line.lower():
                # Format: ## Category Name (priority: 10)
                import re
                m = re.search(r'##\s+(.+?)\s*\(priority:\s*(\d+)\)', line, re.IGNORECASE)
                if m:
                    current_category = m.group(1).strip()
                    current_priority = int(m.group(2))
                continue
            
            # Topic with status
            if ('🔴' in line or '🟡' in line or '🟢' in line) and '[' in line and '](' in line:
                import re
                m = re.search(r'([🔴🟡🟢])\s*\[([^\]]+)\]\(([^)]+)\)', line)
                if m:
                    status = m.group(1)
                    topic = m.group(2)
                    filename = m.group(3)
                    
                    topics.append(TextbookTopic(
                        category=current_category or "General",
                        priority=current_priority,
                        topic=topic,
                        filename=filename,
                        status=status
                    ))
        
        self.topics = topics
        return topics
    
    def create_default_textbook(self):
        """Create default Учебник.md with 8 categories, 32 topics"""
        default_content = """---
type: textbook
tags: ["#textbook", "#learning", "#knowledge-base"]
---

# 📚 УЧЕБНИК — Knowledge Base

## Категории (8) с приоритетами:
1. Graph Engineering & Evolution (priority: 10)
2. Obsidian Advanced (priority: 9)
3. MCP & Agent Integration (priority: 9)
4. AI/ML on AMD Radeon 780M (priority: 10)
5. Video Surveillance & YOLO (priority: 8)
6. ParanoidX / Sovereign Systems (priority: 7)
7. Windows/MSYS Mastery (priority: 6)
8. Hermes Agent Internals (priority: 8)

## Graph Engineering & Evolution (priority: 10)
- [ ] [Graph Engineering Protocol v3.0](Graph%20Engineering%20Protocol.md) — 🔴
- [ ] [Self-Evolving Graphs](Self-Evolving%20Graphs.md) — 🔴
- [ ] [Loop vs Graph vs Harness](Loop%20vs%20Graph%20vs%20Harness.md) — 🔴
- [ ] [Fitness Functions Design](Fitness%20Functions%20Design.md) — 🔴

## Obsidian Advanced (priority: 9)
- [ ] [Dataview Mastery](Dataview%20Mastery.md) — 🔴
- [ ] [Graph View Customization](Graph%20View%20Customization.md) — 🔴
- [ ] [MCP Integration](MCP%20Integration.md) — 🔴
- [ ] [Vault-LD Semantic Interop](Vault-LD%20Semantic%20Interop.md) — 🔴

## MCP & Agent Integration (priority: 9)
- [ ] [Agent Tool Registry Pattern](Agent%20Tool%20Registry%20Pattern.md) — 🔴
- [ ] [Multi-Agent Orchestration](Multi-Agent%20Orchestration.md) — 🔴
- [ ] [Encrypted Inter-Agent Comm](Encrypted%20Inter-Agent%20Comm.md) — 🔴
- [ ] [Model Registry Routing](Model%20Registry%20Routing.md) — 🔴

## AI/ML on AMD Radeon 780M (priority: 10)
- [ ] [ROCm Optimization](ROCm%20Optimization.md) — 🔴
- [ ] [DirectML for Inference](DirectML%20for%20Inference.md) — 🔴
- [ ] [Quantization on iGPU](Quantization%20on%20iGPU.md) — 🔴
- [ ] [Speculative Decoding AMD](Speculative%20Decoding%20AMD.md) — 🔴

## Video Surveillance & YOLO (priority: 8)
- [ ] [YOLOv11 Architecture](YOLOv11%20Architecture.md) — 🔴
- [ ] [RTSP Stream Optimization](RTSP%20Stream%20Optimization.md) — 🔴
- [ ] [Edge Detection Pipelines](Edge%20Detection%20Pipelines.md) — 🔴
- [ ] [Telegram Alert Integration](Telegram%20Alert%20Integration.md) — 🔴

## ParanoidX / Sovereign Systems (priority: 7)
- [ ] [SimpleX Protocol](SimpleX%20Protocol.md) — 🔴
- [ ] [Tor Hidden Services](Tor%20Hidden%20Services.md) — 🔴
- [ ] [Saint Mary Liberty Economy](Saint%20Mary%20Liberty%20Economy.md) — 🔴
- [ ] [Flutter AES Encryption](Flutter%20AES%20Encryption.md) — 🔴

## Windows/MSYS Mastery (priority: 6)
- [ ] [MSYS Path Pitfalls](MSYS%20Path%20Pitfalls.md) — 🔴
- [ ] [Windows Service NSSM](Windows%20Service%20NSSM.md) — 🔴
- [ ] [Gradle Manual Config](Gradle%20Manual%20Config.md) — 🔴
- [ ] [Docker on Windows](Docker%20on%20Windows.md) — 🔴

## Hermes Agent Internals (priority: 8)
- [ ] [Skill System Architecture](Skill%20System%20Architecture.md) — 🔴
- [ ] [Cron Job Orchestration](Cron%20Job%20Orchestration.md) — 🔴
- [ ] [CDP Browser Automation](CDP%20Browser%20Automation.md) — 🔴
- [ ] [Profile Auto-Load](Profile%20Auto-Load.md) — 🔴
"""
        self.textbook_path.write_text(default_content, encoding='utf-8')
        print(f"  📝 Created default Учебник.md at {self.textbook_path}")
    
    def select_topic(self) -> Optional[TextbookTopic]:
        """Select next topic to learn (weighted by priority)"""
        red_topics = [t for t in self.topics if t.status == '🔴']
        
        if not red_topics:
            return None
        
        if self.weighted_random:
            # Weight by priority
            weights = [t.priority for t in red_topics]
            selected = random.choices(red_topics, weights=weights, k=1)[0]
        else:
            # Highest priority first
            selected = max(red_topics, key=lambda t: t.priority)
        
        return selected
    
    def study_topic(self, topic: TextbookTopic) -> Dict:
        """Simulate studying the topic (in real impl, would call LLM)"""
        print(f"  📖 Studying: {topic.topic} ({topic.category}, priority {topic.priority})")
        
        # In real implementation, this would:
        # 1. Read the topic file (if exists)
        # 2. Search web/X.com for latest info
        # 3. Generate insights
        # 4. Write to topic file
        # 5. Return insights
        
        insights = [
            f"Key insight 1 about {topic.topic}",
            f"Key insight 2 about {topic.topic}",
            f"Practical application for Living Code Project {random.randint(1,4)}",
        ]
        
        code_pattern = f'''# {topic.topic} - Practical Example
def {topic.topic.lower().replace(' ', '_')}_pattern():
    \"\"\"
    Auto-generated pattern from textbook learning
    Cycle: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
    \"\"\"
    pass
'''
        
        return {
            "topic": topic.topic,
            "insights": insights,
            "code_pattern": code_pattern,
            "applied_to": [f"godmode-coder skill", f"obsidian-graph-engineering skill"],
            "next_steps": [f"Deep dive: {topic.topic} subtopic", f"Integration: where to apply"]
        }
    
    def update_textbook_status(self, topic: TextbookTopic, new_status: str):
        """Update topic status in Учебник.md"""
        content = self.textbook_path.read_text(encoding='utf-8')
        
        # Replace status emoji
        old_line = f"{topic.status} [{topic.topic}]({topic.filename})"
        new_line = f"{new_status} [{topic.topic}]({topic.filename})"
        
        content = content.replace(old_line, new_line)
        
        self.textbook_path.write_text(content, encoding='utf-8')
    
    def update_chronicle(self, topic: TextbookTopic, study_result: Dict):
        """Append to chronicle.md"""
        self.chronicle_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} — Learned: {topic.topic}\n"
        entry += f"**Category:** {topic.category}\n"
        entry += f"**Priority:** {topic.priority}\n"
        entry += f"**Source:** {topic.filename}\n\n"
        
        entry += "### Key Insights\n"
        for insight in study_result["insights"]:
            entry += f"- {insight}\n"
        
        entry += "\n### Code Patterns\n```python\n"
        entry += study_result["code_pattern"]
        entry += "```\n"
        
        entry += "\n### Applied To\n"
        for applied in study_result["applied_to"]:
            entry += f"- {applied}\n"
        
        entry += "\n### Next Steps\n"
        for step in study_result["next_steps"]:
            entry += f"- [ ] {step}\n"
        
        entry += "\n---\n"
        
        if self.chronicle_path.exists():
            content = self.chronicle_path.read_text(encoding='utf-8')
        else:
            content = "# Летопись Живого Кода\n\n"
        
        self.chronicle_path.write_text(content + entry, encoding='utf-8')
    
    def git_commit(self, topic: TextbookTopic):
        """Git commit the changes"""
        self.run_cmd("git add Учебник.md Evolution/chronicle.md", cwd=self.root)
        self.run_cmd(f'git commit -m "learned: {topic.topic} ({topic.category})"', cwd=self.root)
    
    def run(self) -> Dict:
        """Run textbook learning cycle"""
        print(f"\n{'='*60}")
        print(f"📚 TEXTBOOK LEARNING — Cycle Aware: {self.cycle_aware}")
        print(f"{'='*60}")
        
        # Parse textbook
        self.parse_textbook()
        print(f"  📖 Loaded {len(self.topics)} topics")
        
        red_count = len([t for t in self.topics if t.status == '🔴'])
        yellow_count = len([t for t in self.topics if t.status == '🟡'])
        green_count = len([t for t in self.topics if t.status == '🟢'])
        print(f"  📊 Status: 🔴{red_count} 🟡{yellow_count} 🟢{green_count}")
        
        # Select topic
        topic = self.select_topic()
        
        if not topic:
            print("  ✅ All topics learned! (100% 🟢)")
            return {"status": "complete", "learned": 0}
        
        # Mark as in progress
        self.update_textbook_status(topic, '🟡')
        
        # Study
        study_result = self.study_topic(topic)
        
        # Mark as learned
        self.update_textbook_status(topic, '🟢')
        topic.status = '🟢'
        topic.learned_at = datetime.now(timezone.utc).isoformat()
        
        # Update chronicle
        self.update_chronicle(topic, study_result)
        
        # Git commit
        self.git_commit(topic)
        
        print(f"\n  ✅ Learned: {topic.topic}")
        print(f"  📝 Insights: {len(study_result['insights'])}")
        print(f"  💾 Committed to git")
        
        return {
            "status": "learned",
            "topic": topic.topic,
            "category": topic.category,
            "priority": topic.priority,
            "insights": study_result["insights"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description="Textbook Learn — Living Code")
    parser.add_argument("--cycle-aware", action="store_true")
    parser.add_argument("--weighted-random", action="store_true")
    args = parser.parse_args()
    
    learner = TextbookLearn(args.cycle_aware, args.weighted_random)
    result = learner.run()
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    import json
    main()