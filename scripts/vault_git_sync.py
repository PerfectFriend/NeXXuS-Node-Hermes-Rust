#!/usr/bin/env python3
# Living Code Ecosystem — Vault Git Sync (Daily 04:00)
# Версия: 1.0
# Авто-бэкап Vault и LivingCode репозиториев
# Использование: python vault_git_sync.py

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict

class VaultGitSync:
    def __init__(self):
        self.vault_root = Path("C:/Vault")
        self.living_code_root = Path("C:/LivingCode")
    
    def run_cmd(self, cmd: str, cwd: Path = None, timeout: int = 120) -> tuple:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd or self.vault_root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def sync_repo(self, name: str, path: Path) -> Dict:
        """Sync a single repo"""
        if not path.exists():
            return {"repo": name, "success": False, "error": "Path not found"}
        
        # Check if git repo
        if not (path / ".git").exists():
            return {"repo": name, "success": False, "error": "Not a git repo"}
        
        # Git status
        success, out, err = self.run_cmd("git status --porcelain", cwd=path)
        has_changes = bool(out.strip()) if success else False
        
        if not has_changes:
            return {"repo": name, "success": True, "changed": False, "message": "No changes"}
        
        # Add and commit
        success, out, err = self.run_cmd("git add -A", cwd=path)
        if not success:
            return {"repo": name, "success": False, "error": f"git add failed: {err}"}
        
        commit_msg = f"Auto-backup {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        success, out, err = self.run_cmd(f'git commit -m "{commit_msg}"', cwd=path)
        if not success:
            return {"repo": name, "success": False, "error": f"git commit failed: {err}"}
        
        # Push
        success, out, err = self.run_cmd("git push origin main", cwd=path)
        if not success:
            # Try master branch
            success, out, err = self.run_cmd("git push origin master", cwd=path)
        
        return {
            "repo": name,
            "success": success,
            "changed": True,
            "pushed": success,
            "message": out[:200] if out else err[:200]
        }
    
    def run(self) -> Dict:
        """Run vault git sync"""
        print(f"\n{'='*60}")
        print(f"💾 VAULT GIT SYNC — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"{'='*60}")
        
        repos = [
            ("Vault", self.vault_root),
            ("LivingCode Root", self.living_code_root),
            ("Project1", self.living_code_root / "Project1"),
            ("Project2", self.living_code_root / "Project2"),
            ("Project3", self.living_code_root / "Project3"),
            ("Project4", self.living_code_root / "Project4"),
            ("Grimoire", Path("C:/Users/tomas/the-grimoire")),
        ]
        
        results = []
        for name, path in repos:
            print(f"\n  🔄 Syncing {name}...")
            result = self.sync_repo(name, path)
            results.append(result)
            
            if result["success"]:
                if result.get("changed"):
                    print(f"     ✅ Committed & pushed")
                else:
                    print(f"     ✅ No changes")
            else:
                print(f"     ❌ {result.get('error', 'Failed')}")
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_repos": len(repos),
            "successful": len([r for r in results if r["success"]]),
            "with_changes": len([r for r in results if r.get("changed")]),
            "results": results
        }
        
        print(f"\n{'='*60}")
        print(f"✅ VAULT GIT SYNC COMPLETE: {summary['successful']}/{summary['total_repos']} repos synced")
        print(f"{'='*60}")
        
        return summary


def main():
    sync = VaultGitSync()
    result = sync.run()
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["successful"] == result["total_repos"] else 1)


if __name__ == "__main__":
    main()