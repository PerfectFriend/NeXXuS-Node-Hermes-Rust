#!/usr/bin/env python3
# Living Code Ecosystem — Encrypted Communication Protocol
# Версия: 1.0
# Синхронный круг агентов каждые 10 минут: предсказания, споры, консенсус
# Использование: python encrypted_comm.py --round --cycle 42 | --briefing --cycle 42 | --verify-callback --cycle 42

import argparse
import json
import sys
import os
import base64
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def auto_detect_cycle() -> int:
    """Auto-detect the current cycle based on 4-hour intervals since 2026-01-01."""
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    cycle = int((now - epoch).total_seconds() / 14400)  # 4 hours = 14400 seconds
    return cycle

@dataclass
class Agent:
    id: str
    name: str
    patronymic: str
    role: str

@dataclass
class Message:
    timestamp: str
    cycle: int
    round: Optional[int]
    from_agent: str
    to_agents: List[str]
    message_type: str  # briefing, prediction, debate, consensus, verification, event
    content: str
    content_hash: str

AGENTS = [
    Agent("evolution_p1", "Архитектор", "Сергеевич", "Core Engine Evolution"),
    Agent("evolution_p2", "Инженер", "Дмитриевич", "Integration Evolution"),
    Agent("evolution_p3", "Оптимизатор", "Андреевич", "Performance Evolution"),
    Agent("evolution_p4", "Хранитель", "Михайлович", "Security Evolution"),
    Agent("filter_overlord", "Владыка", "Павлович", "Code Verification"),
]

class EncryptedComm:
    def __init__(self, cycle: int):
        self.cycle = cycle
        self.root = Path("C:/LivingCode")
        self.logs_dir = self.root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir = self.root / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.round_num = 0
        self.cycle_key = self._get_or_create_cycle_key()
    
    def _get_or_create_cycle_key(self) -> bytes:
        """Get or create AES-256 key for this cycle"""
        key_file = self.keys_dir / f"cycle_{self.cycle}_key.bin"
        if key_file.exists():
            return key_file.read_bytes()
        # Generate new key
        key = os.urandom(32)  # 256 bits
        key_file.write_bytes(key)
        return key
    
    def encrypt(self, plaintext: str, associated_data: bytes = b"") -> Dict:
        """Encrypt with AES-256-GCM"""
        aesgcm = AESGCM(self.cycle_key)
        nonce = os.urandom(12)  # 96-bit nonce
        ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), associated_data)
        return {
            "ciphertext": base64.b64encode(ct).decode('ascii'),
            "nonce": base64.b64encode(nonce).decode('ascii'),
            "algorithm": "AES-256-GCM"
        }
    
    def decrypt(self, ciphertext_b64: str, nonce_b64: str, associated_data: bytes = b"") -> str:
        """Decrypt AES-256-GCM"""
        aesgcm = AESGCM(self.cycle_key)
        ct = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
        pt = aesgcm.decrypt(nonce, ct, associated_data)
        return pt.decode('utf-8')
    
    def hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def log_message(self, msg: Message):
        """Log message to JSONL (encrypted content)"""
        log_file = self.logs_dir / f"encrypted_comm_cycle_{self.cycle}.jsonl"
        # Store encrypted version
        associated = f"cycle={self.cycle},round={msg.round or 0},from={msg.from_agent}".encode()
        encrypted = self.encrypt(msg.content, associated)
        
        log_entry = {
            "timestamp": msg.timestamp,
            "cycle": msg.cycle,
            "round": msg.round,
            "from_agent": msg.from_agent,
            "to_agents": msg.to_agents,
            "message_type": msg.message_type,
            "content_encrypted": encrypted,
            "content_hash": msg.content_hash,
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # Also store plaintext for debugging (in real prod, skip this)
        debug_file = self.logs_dir / f"encrypted_comm_cycle_{self.cycle}_debug.jsonl"
        debug_entry = asdict(msg)
        with open(debug_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(debug_entry, ensure_ascii=False) + '\n')
    
    def send_briefing(self):
        """Phase 1: Send briefing to all agents"""
        self.round_num = 0
        content = f"""🔐 ЦИКЛ {self.cycle}/120 — БРИФИНГ
Время: {datetime.now(timezone.utc).isoformat()}
Участники: {', '.join([f'{a.name} {a.patronymic}' for a in AGENTS])}
Задача: Предсказать состояние кода через 210 минут (конец эволюции, T+210min).
Протокол: briefing -> predictions -> debate (если consensus<90%) -> consensus -> verification_callback.
Шифрование: AES-256-GCM, ключ цикла ротируется каждые 4 часа.
Владыка Павлович провалидирует в T+210min."""
        
        msg = Message(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cycle=self.cycle,
            round=0,
            from_agent="encrypted_comm",
            to_agents=[a.id for a in AGENTS],
            message_type="briefing",
            content=content,
            content_hash=self.hash_content(content)
        )
        self.log_message(msg)
        print(f"📢 Briefing sent to {len(AGENTS)} agents")
        return msg
    
    def collect_predictions(self) -> List[Message]:
        """Phase 2: Collect predictions from evolution agents (simulated)"""
        self.round_num = 1
        predictions = []
        
        # In real implementation, this would wait for actual agent responses
        # For now, simulate predictions based on agent roles
        prediction_templates = {
            "evolution_p1": "Архитектор Сергеевич: Мой прогноз — core_engine: READY (0.95). Детали: рефакторинг модуля physics завершён, тесты 247/247 passed. Риски: интеграция с renderer может задержаться на 1 подцикл.",
            "evolution_p2": "Инженер Дмитриевич: Мой прогноз — api_gateway: READY (0.90). Детали: OpenAPI spec v3.1 валидна, интеграционные тесты 89/92 passed (3 flaky). Риски: flaky тесты могут не пройти.",
            "evolution_p3": "Оптимизатор Андреевич: Мой прогноз — render_pipeline: FROZEN (0.98). Детали: уже идеален, 0 изменений 3 подцикла, latency p99=1.2ms. Риски: нет.",
            "evolution_p4": "Хранитель Михайлович: Мой прогноз — auth_module: READY (0.93). Детали: OAuth2+JWT+hW реализован, аудит прошёл. Риски: rotation ключей тестируется.",
            "filter_overlord": "Владыка Павлович: Принимаю прогнозы. Консенсус будет рассчитан после сбора всех предсказаний.",
        }
        
        for agent in AGENTS:
            if agent.id in prediction_templates:
                content = prediction_templates[agent.id]
                msg = Message(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    cycle=self.cycle,
                    round=1,
                    from_agent=agent.id,
                    to_agents=["encrypted_comm", "filter_overlord"],
                    message_type="prediction",
                    content=content,
                    content_hash=self.hash_content(content)
                )
                self.log_message(msg)
                predictions.append(msg)
                print(f"  📥 Prediction from {agent.name} {agent.patronymic}")
        
        return predictions
    
    def run_debate(self, predictions: List[Message]) -> List[Message]:
        """Phase 3: Debate if consensus < 90%"""
        # Calculate consensus (simplified)
        consensus = 94  # Would be calculated from actual predictions
        
        if consensus >= 90:
            print(f"  ✅ Consensus {consensus}% — no debate needed")
            return []
        
        print(f"  ⚔️  Consensus {consensus}% < 90% — initiating debate")
        self.round_num = 2
        debates = []
        
        # Simulated debate
        debate_content = "Архитектор Сергеевич, не согласен с Инженером Дмитриевичем по api_gateway.\nАргумент: flaky тесты указывают на архитектурную проблему, не на баг.\nКонтрум: Инженер Дмитриевич — flaky из-за внешней зависимости, мокаем в следующем подцикле."
        
        msg = Message(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cycle=self.cycle,
            round=2,
            from_agent="evolution_p1",
            to_agents=["evolution_p2", "filter_overlord", "encrypted_comm"],
            message_type="debate",
            content=debate_content,
            content_hash=self.hash_content(debate_content)
        )
        self.log_message(msg)
        debates.append(msg)
        
        # Resolution by Filter Overlord
        resolution = "Владыка Павлович: Аргумент Архитектора принят. Инженер Дмитриевич — замокать зависимость в подцикле 8. Консенсус обновлён: 96%."
        msg2 = Message(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cycle=self.cycle,
            round=2,
            from_agent="filter_overlord",
            to_agents=["all"],
            message_type="debate",
            content=resolution,
            content_hash=self.hash_content(resolution)
        )
        self.log_message(msg2)
        debates.append(msg2)
        
        return debates
    
    def announce_consensus(self, predictions: List[Message], debates: List[Message]):
        """Phase 4: Announce consensus"""
        self.round_num = 3
        consensus = 96  # After debate
        
        content = f"""🔐 КОНСЕНСУС ДОСТИГНУТ ({consensus}%)
Финальные предсказания зафиксированы в Хронике.
Владыка Павлович, просьба верифицировать в T+210min (через {210 - (self.round_num * 10)} минут).
READY компоненты будут переданы Художнику Георгиевичу для баннеров.
DJ студийонок Витальевич — на аудио для game компонентов.
СвятоТворец Всеволодович — готовьте финальную сборку."""
        
        msg = Message(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cycle=self.cycle,
            round=3,
            from_agent="encrypted_comm",
            to_agents=[a.id for a in AGENTS] + ["banner_deploy", "dj_sound_studio", "holy_code_apps"],
            message_type="consensus",
            content=content,
            content_hash=self.hash_content(content)
        )
        self.log_message(msg)
        print(f"  🤝 Consensus announced: {consensus}%")
    
    def run_round(self):
        """Run one complete 10-minute round"""
        print(f"\n{'='*60}")
        print(f"🔐 ENCRYPTED COMM — Cycle {self.cycle} Round {self.round_num + 1}/19")
        print(f"{'='*60}")
        
        # Phase 1: Briefing (only on round 0)
        if self.round_num == 0:
            self.send_briefing()
        
        # Phase 2: Predictions
        predictions = self.collect_predictions()
        
        # Phase 3: Debate if needed
        debates = self.run_debate(predictions)
        
        # Phase 4: Consensus
        self.announce_consensus(predictions, debates)
        
        print(f"\n✅ Round {self.round_num} complete. Next round in 10 minutes.")
    
    def verification_callback(self, filter_report: Dict):
        """Phase 5: Verification callback from Filter Overlord"""
        ready = filter_report.get("summary", {}).get("ready", 0)
        frozen = filter_report.get("summary", {}).get("frozen", 0)
        archived = filter_report.get("summary", {}).get("archived", 0)
        match_pct = filter_report.get("match_pct", 0)
        
        content = f"""Владыка Павлович, верификация завершена.
READY: {ready} компонентов
FROZEN: {frozen} компонентов  
ARCHIVED: {archived} компонентов
Соответствует прогнозу: {match_pct}%
Художник Георгиевич — на баннеры для READY.
DJ студийонок Витальевич — аудио для game READY.
СвятоТворец Всеволодович — финальная сборка в сторы."""
        
        msg = Message(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cycle=self.cycle,
            round=None,
            from_agent="filter_overlord",
            to_agents=["encrypted_comm", "banner_deploy", "dj_sound_studio", "holy_code_apps"],
            message_type="verification",
            content=content,
            content_hash=self.hash_content(content)
        )
        self.log_message(msg)
        print(f"📥 Verification callback logged")


def main():
    parser = argparse.ArgumentParser(description="Encrypted Communication Protocol")
    parser.add_argument("--cycle", type=int, help="Cycle number (auto-detected if omitted)")
    parser.add_argument("--round", action="store_true", help="Run one 10-min round")
    parser.add_argument("--briefing", action="store_true", help="Send cycle briefing only")
    parser.add_argument("--verify-callback", action="store_true", help="Process verification callback")
    parser.add_argument("--report-file", type=str, help="Filter report JSON file for callback")
    args = parser.parse_args()

    # Auto-detect cycle if not provided
    cycle = args.cycle
    if cycle is None:
        cycle = auto_detect_cycle()
        print(f"���� Auto-detected cycle: {cycle}")

    comm = EncryptedComm(cycle)

    # Default to --round if no action specified (for cron compatibility)
    action = None
    if args.briefing:
        action = "briefing"
    elif args.round:
        action = "round"
    elif args.verify_callback and args.report_file:
        action = "verify_callback"
    elif not any([args.briefing, args.round, args.verify_callback]):
        # No action flag provided — default to round for cron jobs
        action = "round"
        print("�����  No action flag provided, defaulting to --round")

    if action == "briefing":
        comm.send_briefing()
    elif action == "round":
        comm.run_round()
    elif action == "verify_callback":
        with open(args.report_file) as f:
            report = json.load(f)
        comm.verification_callback(report)
    else:
        print("Use --round, --briefing, or --verify-callback --report-file")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()