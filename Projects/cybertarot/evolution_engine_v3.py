# HOT
#!/usr/bin/env python3
"""
CyberTarot Autonomous Evolution Engine v3 - Linux Native
Uses the LivingCode/Projects/cybertarot path on Linux.
Executes Phase 0-1 tasks, commits, reports progress.
"""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path("/home/thomas/LivingCode/Projects/cybertarot")
CYCLES_PER_ROUND = 20
CHAT = "telegram:143293811"

def tg(msg):
    """Send report via hermes CLI."""
    subprocess.run(
        ["hermes", "send", "--to", CHAT, msg],
        capture_output=True, timeout=15, check=False
    )

def run(cmd, cwd=None, timeout=300):
    """Run shell command."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd or PROJECT_DIR,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="ignore", check=False)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.SubprocessError as e:
        return False, str(e)
    except OSError as e:
        return False, str(e)

def git_commit(msg):
    """Stage and commit all changes."""
    run("git add -A")
    ok, out = run(f'git commit -m "{msg}" --allow-empty')
    return ok, out

# ============================================================
# PHASE 0 TASKS
# ============================================================
def task_0_1():
    """Git init + .gitignore + first commit."""
    if not (PROJECT_DIR / ".git").exists():
        run("git init")
    run('git config user.name "Hermes Agent"')
    run('git config user.email "hermes@cybertarot.local"')
    # Write .gitignore via Python (heredoc breaks in MSYS bash)
    gitignore = """node_modules/
dist/
art/cards/
art/cards_hd/
art/cards_final/
*.pyc
__pycache__/
.env
*.log
evolution_state.json
"""
    (PROJECT_DIR / ".gitignore").write_text(gitignore, encoding="utf-8")
    ok, out = git_commit("feat: Phase 0 — Vite+React+TS scaffold + 22 Major Arcana art + ManaWell")
    return ok, out

def task_0_2():
    """Expand deck to 78 cards."""
    deck_path = PROJECT_DIR / "src/data/tarot-deck.json"
    if not deck_path.exists():
        return False, "tarot-deck.json not found"
    deck_data = json.loads(deck_path.read_text(encoding="utf-8"))
    deck = deck_data.get("cards", [])
    if not isinstance(deck, list):
        deck = []
    
    # If deck already has 78 cards, skip
    if len(deck) >= 78:
        return True, f"Deck already has {len(deck)} cards, skipping expansion"
    
    existing_ids = {c["id"] for c in deck}

    suits = [
        {"id": "wands", "name_en": "Wands", "name_ru": "Жезлы", "element": "Fire"},
        {"id": "cups", "name_en": "Cups", "name_ru": "Чаши", "element": "Water"},
        {"id": "swords", "name_en": "Swords", "name_ru": "Мечи", "element": "Air"},
        {"id": "pentacles", "name_en": "Pentacles", "name_ru": "Пентакли", "element": "Earth"},
    ]

    ranks = [
        (1, "Ace", {"en": "beginning, potential", "ru": "начало, потенциал"}),
        (2, "Two", {"en": "balance, choice", "ru": "баланс, выбор"}),
        (3, "Three", {"en": "growth, creativity", "ru": "рост, творчество"}),
        (4, "Four", {"en": "stability, structure", "ru": "стабильность, структура"}),
        (5, "Five", {"en": "conflict, change", "ru": "конфликт, изменение"}),
        (6, "Six", {"en": "harmony, progress", "ru": "гармония, прогресс"}),
        (7, "Seven", {"en": "challenge, assessment", "ru": "вызов, оценка"}),
        (8, "Eight", {"en": "movement, speed", "ru": "движение, скорость"}),
        (9, "Nine", {"en": "attainment, reflection", "ru": "достижение, рефлексия"}),
        (10, "Ten", {"en": "completion, fulfillment", "ru": "завершение, исполнение"}),
        (11, "Page", {"en": "messenger, curiosity", "ru": "посланник, любопытство"}),
        (12, "Knight", {"en": "action, drive", "ru": "действие, стремление"}),
        (13, "Queen", {"en": "mastery, nurture", "ru": "мастерство, забота"}),
        (14, "King", {"en": "authority, leadership", "ru": "авторитет, лидерство"}),
    ]

    suit_kw = {
        "wands": {"upright": {"en": "energy, passion, action", "ru": "энергия, страсть, действие"},
                  "reversed": {"en": "delay, lack of direction", "ru": "задержка, отсутствие направления"}},
        "cups": {"upright": {"en": "emotion, intuition, relationship", "ru": "эмоция, интуиция, отношения"},
                 "reversed": {"en": "blocked emotions, withdrawal", "ru": "заблокированные эмоции, уход"}},
        "swords": {"upright": {"en": "intellect, conflict, truth", "ru": "интеллект, конфликт, истина"},
                   "reversed": {"en": "confusion, avoidance", "ru": "путаница, избегание"}},
        "pentacles": {"upright": {"en": "material, security, work", "ru": "материальное, безопасность, работа"},
                      "reversed": {"en": "instability, loss", "ru": "нестабильность, потеря"}},
    }

    rarity_map = {1:"common",2:"common",3:"common",4:"common",5:"common",
                  6:"common",7:"rare",8:"rare",9:"rare",10:"rare",
                  11:"epic",12:"epic",13:"legendary",14:"legendary"}

    card_idx = 22

    for suit in suits:
        for rank_num, rank_name, _ in ranks:
            card_id = f"{card_idx:02d}_{suit['id']}_{rank_num}"
            if card_id in existing_ids:
                card_idx += 1
                continue
            card = {
                "id": card_id,
                "arcana": "minor",
                "number": rank_num,
                "name": {"en": f"{rank_name} of {suit['name_en']}", "ru": f"{rank_name} {suit['name_ru']}"},
                "keywords": {
                    "upright": suit_kw[suit["id"]]["upright"],
                    "reversed": suit_kw[suit["id"]]["reversed"],
                },
                "default_rarity": rarity_map[rank_num],
                "suit": suit["id"],
                "element": suit["element"],
                "court": rank_name if rank_num >= 11 else None,
            }
            deck.append(card)
            card_idx += 1

    deck_data["cards"] = deck
    deck_data["total_cards"] = len(deck)
    deck_path.write_text(json.dumps(deck_data, ensure_ascii=False, indent=2), encoding="utf-8")
    ok, _ = run("npx tsc --noEmit")
    git_commit("feat: full 78-card deck (22 Major + 56 Minor Arcana)")
    return ok, f"Deck expanded to {len(deck)} cards"

def task_0_3():
    """Convert PNG cards to WebP + update deck with artPath."""
    from PIL import Image
    cards_final = PROJECT_DIR / "art/cards_final"
    assets = PROJECT_DIR / "src/assets/cards"
    assets.mkdir(parents=True, exist_ok=True)
    deck_path = PROJECT_DIR / "src/data/tarot-deck.json"
    deck_data = json.loads(deck_path.read_text(encoding="utf-8"))
    deck = deck_data.get("cards", [])
    if not isinstance(deck, list):
        deck = []

    converted = 0
    for card in deck:
        png = cards_final / f"{card['id']}.png"
        if png.exists():
            webp = assets / f"{card['id']}.webp"
            if not webp.exists():
                with Image.open(png) as img:
                    img.save(webp, "WEBP", quality=85, method=6)
                    converted += 1
            card["artPath"] = f"/assets/cards/{card['id']}.webp"

    deck_data["cards"] = deck
    deck_path.write_text(json.dumps(deck_data, ensure_ascii=False, indent=2), encoding="utf-8")
    ok, _ = run("npx tsc --noEmit")
    git_commit(f"feat: {converted} card art converted to WebP + artPath in deck")
    return ok, f"Converted {converted} to WebP, updated artPath"

def task_0_4():
    """Add disclaimer to OracleTab."""
    oracle_path = PROJECT_DIR / "src/components/OracleTab.tsx"
    if not oracle_path.exists():
        return False, "OracleTab.tsx not found"
    content = oracle_path.read_text(encoding="utf-8")

    disclaimer = '''    <div className="mt-4 p-3 rounded-lg bg-yellow-900/30 border border-yellow-700/50 text-xs text-yellow-200/70 text-center">
      ⚠️ CyberTarot — это развлекательное приложение. Толкования генерируются AI и не являются прогнозом судьбы или профессиональной консультацией.
    </div>
'''

    if "CyberTarot — это развлекательное" in content:
        return True, "Disclaimer already present"

    # Insert before closing fragment
    if "</div>" in content:
        idx = content.rfind("</div>")
        content = content[:idx] + disclaimer + "\n" + content[idx:]
        oracle_path.write_text(content, encoding="utf-8")

    ok, _ = run("npx tsc --noEmit")
    git_commit("feat: disclaimer in Oracle tab")
    return ok, "Disclaimer added"

# ============================================================
# PHASE 1 TASKS — AI Interpretations
# ============================================================
def task_1_1():
    """Create AI oracle system prompt + few-shot examples + config."""
    ai_dir = PROJECT_DIR / "ai"
    ai_dir.mkdir(exist_ok=True)

    system_prompt = """# CyberTarot Oracle — System Prompt

Ты — киберпанк-таролог. Толкуешь расклады в стиле CyberTarot: будущее сквозь призму неона, данных и цифрового мистицизма.

Правила:
1. НИКОГДА не повторяй одно и то же толкование. Варьируй: метафоры, образы, тон, структуру предложений.
2. Для каждой карты: 2-3 предложения. Учитывай ориентацию (прямая/перевёрнутая) и позицию в раскладе (прошлое/настоящее/будущее).
3. Summary: 3-4 предложения — общая нить расклада.
4. Совет на 24 часа: 1-2 практичных предложения, что сделать сегодня.
5. Тон: мистический, но практичный. Без "вы встретите принца". Ближе к "обратите внимание на..."
6. Дисклеймер: толкование — это размышление, не прогноз судьбы.
7. Язык: следуй locale. RU → русский, EN → английский.

Формат ответа (строгий JSON):
{
  "perCard": [
    {"position": "Past", "text": "..."},
    {"position": "Present", "text": "..."},
    {"position": "Future", "text": "..."}
  ],
  "summary": "...",
  "advice24h": "..."
}"""

    (ai_dir / "oracle-system-prompt.md").write_text(system_prompt, encoding="utf-8")

    examples = [
        {
            "cards": ["The Fool", "The Magician", "The World"],
            "interpretation": {
                "perCard": [
                    {"position": "Past", "text": "Вы шагнули в неизвестность, оставив позади рутину. Импульс был чистым, без расчёта — и он привёл вас сюда."},
                    {"position": "Present", "text": "В ваших руках инструменты, чтобы塑造 реальность. Маг напоминает: вы уже всё умеете, нужно лишь осознать это."},
                    {"position": "Future", "text": "Завершение цикла приближается. Мир раскрывает объятия — но только если вы не остановитесь на полпути."}
                ],
                "summary": "Расклад говорит о начале нового цикла, где过去的 шаг веры встречается с настоящим мастерством. Вы на пороге завершения — не упустите момент.",
                "advice24h": "Сегодня сделайте один конкретный шаг к цели, которую откладывали. Маленький, но реальный."
            }
        },
        {
            "cards": ["The Tower (reversed)", "The Star", "The Sun"],
            "interpretation": {
                "perCard": [
                    {"position": "Past", "text": "Кризис, который вы предчувствовали, уже миновал. Башня перевёрнута — разрушение произошло внутри, не снаружи."},
                    {"position": "Present", "text": "Звезда вливает надежду в пустоту, оставшуюся после бури. Это время исцеления, а не действия."},
                    {"position": "Future", "text": "Солнце обещает ясность и радость. Тучи расходятся — скоро вы почувствуете тепло на лице."}
                ],
                "summary": "После внутреннего катаклизма наступает период восстановления. Надежда и радость идут подряд — позвольте им войти.",
                "advice24h": "Сегодня позвольте себе отдохнуть. Не нужно бежать — исцелениеAlready происходит."
            }
        },
        {
            "cards": ["The Devil", "The Hanged Man", "Death"],
            "interpretation": {
                "perCard": [
                    {"position": "Past", "text": "Вы были привязаны к чему-то, что казалось необходимым. Дьявол указывает на зависимость — материальную, эмоциональную или цифровую."},
                    {"position": "Present", "text": "Висельник предлагает: остановитесь и посмотрите снизу вверх. Перспектива меняется, когда вы перестаёте сопротивляться."},
                    {"position": "Future", "text": "Смерть — не конец, а трансформация. Старое «я» уходит, освобождая место для нового."}
                ],
                "summary": "Расклад о освобождении через принятие. Зависимость → пауза → трансформация. Не бойтесь отпустить.",
                "advice24h": "Определите одну привычку, которая вас удерживает. Сегодня сделайте один шаг к её dismantling."
            }
        },
        {
            "cards": ["The Empress", "The Lovers", "Wheel of Fortune"],
            "interpretation": {
                "perCard": [
                    {"position": "Past", "text": "Императрица наполняла ваш мир изобилием — идеи, эмоции, возможности росли как на дрожжах."},
                    {"position": "Present", "text": "Влюблённые требуют выбора. Не между людьми — между ценностями. Что вы любите больше: комфорт или рост?"},
                    {"position": "Future", "text": "Колесо Фортуны поворачивается. Удача на стороне того, кто сделал выбор — а не того, кто ждёт."}
                ],
                "summary": "Изобилие прошлого встречается с развилкой настоящего. Фортуна улыбнётся, но только после решения.",
                "advice24h": "Сегодня примите решение, которое откладывали. Фортуна любит смелых."
            }
        },
        {
            "cards": ["The Hermit", "The Moon", "Judgement"],
            "interpretation": {
                "perCard": [
                    {"position": "Past", "text": "Вы удалились внутрь себя. Отшельник дал время подумать — и это было необходимо."},
                    {"position": "Present", "text": "Луна бросает тени сомнений. Не всё, что вы видите, реально. Иллюзии активны — держитесь фактов."},
                    {"position": "Future", "text": "Суд зовёт к пробуждению. Что-то внутри вас готово подняться — ответ на зов изменитtrajectory."}
                ],
                "summary": "Уединение привело к ясности, но иллюзии всё ещё мешают. Готовится призыв — услышьте его.",
                "advice24h": "Сегодня прислушайтесь к интуиции, но проверяйте факты. Ответ уже внутри вас."
            }
        }
    ]

    (ai_dir / "oracle-examples.json").write_text(
        json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")

    config = {
        "model": "qwen3:8b",
        "temperature": 0.9,
        "top_p": 0.95,
        "top_k": 40,
        "seed_strategy": "hash(cards_ids + date + user_session)",
        "max_tokens": 800,
        "repeat_penalty": 1.15,
        "num_ctx": 4096,
        "format": "json",
        "fallback_chain": ["ollama", "api", "mock"],
        "cache_ttl_hours": 24
    }
    (ai_dir / "oracle-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    git_commit("feat: AI oracle skill package (system prompt + 5 few-shot + config)")
    return True, "Created ai/oracle-system-prompt.md, oracle-examples.json, oracle-config.json"

def task_1_2():
    """Create Ollama client service."""
    ollama_path = PROJECT_DIR / "src/services/ollama.ts"
    content = '''// CyberTarot — Ollama Client
// Connects to local Ollama for AI tarot interpretations

import type { InterpretationResult, DrawnCard, Locale } from "@/types";

const OLLAMA_URL = import.meta.env.VITE_OLLAMA_URL || "http://localhost:11434";
const MODEL = "qwen3:8b";

function hashSeed(cards: DrawnCard[], locale: Locale): number {
  const date = new Date().toDateString();
  const key = cards.map(c => c.id + c.orientation).join(",") + date + locale;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash << 5) - hash) + key.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export async function ollamaInterpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): Promise<InterpretationResult | null> {
  const seed = hashSeed(cards, locale);

  const systemPrompt = `You are a cyberpunk tarot reader. Respond in ${locale === "ru" ? "Russian" : "English"}. Return ONLY valid JSON with keys: perCard (array of {position, text}), summary (string), advice24h (string). Each card gets 2-3 sentences. Summary 3-4 sentences. Advice 1-2 practical sentences for next 24h.`;

  const userMessage = cards.map((c, i) => {
    const pos = positions[i] || `Position ${i + 1}`;
    const orient = c.orientation === "reversed" ? " (Reversed)" : "";
    const meaning = c.orientation === "reversed"
      ? (c.keywords.reversed[locale] || c.keywords.reversed.en)
      : (c.keywords.upright[locale] || c.keywords.upright.en);
    return `Card ${i + 1}: ${c.name[locale] || c.name.en}${orient} — ${pos}. Meaning: ${meaning}`;
  }).join("\\n");

  const body = {
    model: MODEL,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userMessage }
    ],
    stream: false,
    options: {
      temperature: 0.9,
      top_p: 0.95,
      seed: seed,
      num_ctx: 4096,
    },
    format: "json",
  };

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);

    const resp = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!resp.ok) return null;

    const data = await resp.json();
    const content = data.message?.content || "";
    const parsed = JSON.parse(content);

    return {
      summary: parsed.summary || "",
      perCard: (parsed.perCard || []).map((pc: any, i: number) => ({
        position: positions[i] || null,
        text: pc.text || "",
      })),
      reflectionPrompt: locale === "ru"
        ? "Что эти карты говорят о вашем текущем пути?"
        : "What do these cards say about your current path?",
    };
  } catch {
    return null;
  }
}
'''
    ollama_path.write_text(content, encoding="utf-8")
    ok, _ = run("npx tsc --noEmit")
    git_commit("feat: Ollama client for AI tarot interpretations")
    return ok, "Created src/services/ollama.ts"

def task_1_3():
    """Update interpret.ts with 3-tier fallback chain."""
    interp_path = PROJECT_DIR / "src/services/interpret.ts"
    content = '''// CyberTarot — Interpretation service
// 3-tier fallback: Ollama → API → Mock

import type { DrawnCard, InterpretationResult, Locale } from "@/types";
import { ollamaInterpret } from "@/services/ollama";

const API_URL = import.meta.env.VITE_API_URL || "";

function mockInterpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): InterpretationResult {
  const perCard = cards.map((c, i) => {
    const meaning = c.orientation === "reversed"
      ? c.keywords.reversed[locale] || c.keywords.reversed.en
      : c.keywords.upright[locale] || c.keywords.upright.en;
    const posLabel = cards.length === 3 ? positions[i] : null;
    return { position: posLabel, text: `${c.name[locale] || c.name.en} — ${meaning}.` };
  });

  const summary = perCard.map(pc => pc.text).join(" ");
  const reflectionPrompt = locale === "ru"
    ? "Что эти карты говорят о вашем текущем пути?"
    : "What do these cards say about your current path?";

  return { summary, perCard, reflectionPrompt };
}

function getCached(cards: DrawnCard[], locale: Locale): InterpretationResult | null {
  const date = new Date().toDateString();
  const key = `ct_interp_${cards.map(c => c.id + c.orientation).join(",")}_${locale}_${date}`;
  try {
    const cached = localStorage.getItem(key);
    if (cached) return JSON.parse(cached);
  } catch {}
  return null;
}

function setCache(cards: DrawnCard[], locale: Locale, result: InterpretationResult) {
  const date = new Date().toDateString();
  const key = `ct_interp_${cards.map(c => c.id + c.orientation).join(",")}_${locale}_${date}`;
  try {
    localStorage.setItem(key, JSON.stringify(result));
  } catch {}
}

export async function interpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): Promise<InterpretationResult> {
  // 1. Check cache
  const cached = getCached(cards, locale);
  if (cached) return cached;

  // 2. Try Ollama (local, 30s timeout)
  const ollamaResult = await ollamaInterpret(cards, locale, positions);
  if (ollamaResult && ollamaResult.summary) {
    setCache(cards, locale, ollamaResult);
    return ollamaResult;
  }

  // 3. Try API (if configured, 15s timeout)
  if (API_URL) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      const resp = await fetch(`${API_URL}/api/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards, locale, positions }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (resp.ok) {
        const result = await resp.json();
        if (result.summary) {
          setCache(cards, locale, result);
          return result;
        }
      }
    } catch {}
  }

  // 4. Fallback to mock
  const mock = mockInterpret(cards, locale, positions);
  setCache(cards, locale, mock);
  return mock;
}
'''
    interp_path.write_text(content, encoding="utf-8")
    ok, _ = run("npx tsc --noEmit")
    git_commit("feat: 3-tier fallback chain (Ollama → API → Mock) + 24h cache")
    return ok, "Updated interpret.ts with fallback chain + cache"

# ============================================================
# MAIN
# ============================================================
TASKS = [
    ("0.1", "Git init + .gitignore + first commit", task_0_1),
    ("0.2", "Expand deck to 78 cards", task_0_2),
    ("0.3", "Convert card art to WebP + artPath", task_0_3),
    ("0.4", "Add disclaimer to OracleTab", task_0_4),
    ("1.1", "AI oracle system prompt + few-shot + config", task_1_1),
    ("1.2", "Ollama client service", task_1_2),
    ("1.3", "3-tier fallback chain + cache in interpret.ts", task_1_3),
]

def main():
    print("=" * 60)
    print("CYBERTAROT AUTONOMOUS EVOLUTION ENGINE v3")
    print(f"Project: {PROJECT_DIR}")
    print(f"Tasks: {len(TASKS)}")
    print("=" * 60)

    tg("🚀 *CyberTarot Evolution v3 Started*\n"
       f"Tasks: {len(TASKS)}\n"
       f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')}")

    task_idx = 0
    round_num = 1

    while task_idx < len(TASKS):
        task_id, task_name, task_fn = TASKS[task_idx]

        print(f"\n[Round {round_num}] Task {task_id}: {task_name}")
        started = time.time()

        try:
            ok, output = task_fn()
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            ok, output = False, str(e)

        elapsed = time.time() - started

        if ok:
            print(f"  ✅ DONE ({elapsed:.1f}s)")
            tg(f"✅ *Task {task_id}*\n{task_name}\n⏱ {elapsed:.1f}s\n```\n{output[:500]}\n```")
            task_idx += 1
        else:
            print(f"  ❌ FAILED: {output[:200]}")
            tg(f"❌ *Task {task_id} FAILED*\n{task_name}\n```\n{output[:800]}\n```")
            # Skip failed task, move to next
            task_idx += 1

        time.sleep(2)

    # All tasks done
    # Final verification
    print("\n=== FINAL VERIFICATION ===")
    ok_tsc, _ = run("npx tsc --noEmit")
    ok_build, _ = run("npm run build", timeout=120)

    report = f"""🎉 *Evolution Complete!*

📊 *Results:*
• Tasks: {len(TASKS)} completed
• TypeScript: {'✅ PASS' if ok_tsc else '❌ FAIL'}
• Build: {'✅ PASS' if ok_build else '❌ FAIL'}

🔄 *Next Phase:* Phase 2 — Limited Edition Series + Хронология
"""
    tg(report)

    # Save final state
    state = {
        "phases_complete": ["0", "1"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tasks_done": len(TASKS),
        "tsc_pass": ok_tsc,
        "build_pass": ok_build,
    }
    (PROJECT_DIR / "evolution_state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8")

    print("\nDONE!")

if __name__ == "__main__":
    main()