

import type { CardData, LocaleConfig, RarityConfig, Rarity } from "@/types";
import deckJson from "@/data/tarot-deck.json";

export const DECK: CardData[] = deckJson.cards as CardData[];
export const TOTAL_CARDS = DECK.length;

export const RARITIES: Record<Rarity, RarityConfig> = {
  common: {
    label: { en: "Common", ru: "Обычная" },
    color: "#7C8199",
    glow: "rgba(124,129,153,0.35)",
    weight: 0,
    cost: 0,
  },
  rare: {
    label: { en: "Rare", ru: "Редкая" },
    color: "#22D3C8",
    glow: "rgba(34,211,200,0.45)",
    weight: 0.7,
    cost: 40,
  },
  epic: {
    label: { en: "Epic", ru: "Эпическая" },
    color: "#8C6CFF",
    glow: "rgba(140,108,255,0.5)",
    weight: 0.25,
    cost: 120,
  },
  legendary: {
    label: { en: "Legendary", ru: "Легендарная" },
    color: "#E8B94A",
    glow: "rgba(232,185,74,0.55)",
    weight: 0.05,
    cost: 400,
  },
};

export const LOCALES: Record<string, LocaleConfig> = {
  en: {
    name: "English",
    app: "CyberTarot",
    tag: "Sequence memory of your fate, dealt by AI",
    draw: "Draw a spread",
    one: "1 card",
    three: "3 cards",
    balance: "Magic",
    ref: "Referral",
    tabs: ["Oracle", "Collection", "Mint", "Market"],
    mintBtn: "Mint a card",
    mintCost: "cost",
    earn: "Earn daily activity (+12 Magic)",
    copy: "Copy code",
    copied: "Copied",
    reversedTag: "reversed",
    uprightTag: "upright",
    positions: ["Present", "Challenge", "Outcome"],
  },
  ru: {
    name: "Русский",
    app: "CyberTarot",
    tag: "Секвенция твоей судьбы, разложенная ИИ",
    draw: "Сделать расклад",
    one: "1 карта",
    three: "3 карты",
    balance: "Magic",
    ref: "Реферал",
    tabs: ["Оракул", "Коллекция", "Минт", "Рынок"],
    mintBtn: "Заминтить карту",
    mintCost: "цена",
    earn: "Заработать активность (+12 Magic)",
    copy: "Скопировать код",
    copied: "Скопировано",
    reversedTag: "перевёрнута",
    uprightTag: "прямое положение",
    positions: ["Настоящее", "Вызов", "Итог"],
  },
  es: {
    name: "Español",
    app: "CyberTarot",
    tag: "La secuencia de tu destino, tirada por IA",
    draw: "Hacer tirada",
    one: "1 carta",
    three: "3 cartas",
    balance: "Magic",
    ref: "Referido",
    tabs: ["Oráculo", "Colección", "Acuñar", "Mercado"],
    mintBtn: "Acuñar carta",
    mintCost: "costo",
    earn: "Ganar actividad diaria (+12 Magic)",
    copy: "Copiar código",
    copied: "Copiado",
    reversedTag: "invertida",
    uprightTag: "derecha",
    positions: ["Presente", "Desafío", "Resultado"],
  },
  zh: {
    name: "中文",
    app: "CyberTarot",
    tag: "由 AI 排列的命运序列",
    draw: "开始占卜",
    one: "1 张牌",
    three: "3 张牌",
    balance: "Magic",
    ref: "推荐码",
    tabs: ["神谕", "收藏", "铸造", "市场"],
    mintBtn: "铸造卡牌",
    mintCost: "花费",
    earn: "获得每日活跃 (+12 Magic)",
    copy: "复制代码",
    copied: "已复制",
    reversedTag: "逆位",
    uprightTag: "正位",
    positions: ["现在", "挑战", "结果"],
  },
  hi: {
    name: "हिन्दी",
    app: "CyberTarot",
    tag: "AI द्वारा बिछाया गया आपकी नियति का क्रम",
    draw: "स्प्रेड करें",
    one: "1 कार्ड",
    three: "3 कार्ड",
    balance: "Magic",
    ref: "रेफ़रल",
    tabs: ["ओरेकल", "संग्रह", "मिंट", "बाज़ार"],
    mintBtn: "कार्ड मिंट करें",
    mintCost: "लागत",
    earn: "दैनिक गतिविधि अर्जित करें (+12 Magic)",
    copy: "कोड कॉपी करें",
    copied: "कॉपी हुआ",
    reversedTag: "उलटा",
    uprightTag: "सीधा",
    positions: ["वर्तमान", "चुनौती", "परिणाम"],
  },
  ar: {
    name: "العربية",
    app: "CyberTarot",
    tag: "تسلسل قدرك، موزّع بواسطة الذكاء الاصطناعي",
    draw: "اسحب توزيعة",
    one: "بطاقة واحدة",
    three: "3 بطاقات",
    balance: "Magic",
    ref: "الإحالة",
    tabs: ["الوحي", "المجموعة", "السك", "السوق"],
    mintBtn: "سك بطاقة",
    mintCost: "التكلفة",
    earn: "اكسب نشاط يومي (+12 Magic)",
    copy: "نسخ الكود",
    copied: "تم النسخ",
    reversedTag: "مقلوبة",
    uprightTag: "معتدلة",
    positions: ["الحاضر", "التحدي", "النتيجة"],
  },
  pt: {
    name: "Português",
    app: "CyberTarot",
    tag: "A sequência do seu destino, tirada por IA",
    draw: "Fazer tiragem",
    one: "1 carta",
    three: "3 cartas",
    balance: "Magic",
    ref: "Indicação",
    tabs: ["Oráculo", "Coleção", "Cunhar", "Mercado"],
    mintBtn: "Cunhar carta",
    mintCost: "costo",
    earn: "Ganhar atividade diária (+12 Magic)",
    copy: "Copiar código",
    copied: "Copiado",
    reversedTag: "invertida",
    uprightTag: "normal",
    positions: ["Presente", "Desafio", "Resultado"],
  },
  ja: {
    name: "日本語",
    app: "CyberTarot",
    tag: "AIが配る、あなたの運命のシーケンス",
    draw: "スプレッドを引く",
    one: "1枚",
    three: "3枚",
    balance: "Magic",
    ref: "紹介コード",
    tabs: ["オラクル", "コレクション", "ミント", "マーケット"],
    mintBtn: "カードをミント",
    mintCost: "コスト",
    earn: "毎日アクティビティ獲得 (+12 Magic)",
    copy: "コードをコピー",
    copied: "コピーしました",
    reversedTag: "逆位置",
    uprightTag: "正位置",
    positions: ["現在", "課題", "結果"],
  },
  fr: {
    name: "Français",
    app: "CyberTarot",
    tag: "La séquence de votre destin, tirée par l'IA",
    draw: "Faire un tirage",
    one: "1 carte",
    three: "3 cartes",
    balance: "Magic",
    ref: "Parrainage",
    tabs: ["Oracle", "Collection", "Frapper", "Marché"],
    mintBtn: "Frapper une carte",
    mintCost: "коût",
    earn: "Gagner activité quotidienne (+12 Magic)",
    copy: "Copier le code",
    copied: "Copié",
    reversedTag: "inversée",
    uprightTag: "droite",
    positions: ["Présent", "Défi", "Résultat"],
  },
  de: {
    name: "Deutsch",
    app: "CyberTarot",
    tag: "Die von KI gelegte Sequenz deines Schicksals",
    draw: "Karten legen",
    one: "1 Karte",
    three: "3 Karten",
    balance: "Magic",
    ref: "Empfehlung",
    tabs: ["Orakel", "Sammlung", "Prägen", "Markт"],
    mintBtn: "Karte prägen",
    mintCost: "Kosten",
    earn: "Tägliche Aktivität verdienen (+12 Magic)",
    copy: "Code kopieren",
    copied: "Kopiert",
    reversedTag: "umgekehrt",
    uprightTag: "aufrecht",
    positions: ["Gegenwart", "Herausforderung", "Ergebnis"],
  },
};

export function rollRarity(): Rarity {
  const r = Math.random();
  if (r < RARITIES.legendary.weight) return "legendary";
  if (r < RARITIES.legendary.weight + RARITIES.epic.weight) return "epic";
  return "rare";
}

export function shuffleDeck(count: number): DrawnCard[] {
  // Use FULL 78-card deck, not just 22 majors.
  // Unbiased Fisher-Yates (Array.prototype.sort(() => Math.random()-0.5) is biased
  // and, for count<78, further skews which cards tend to surface).
  const arr = [...DECK];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  const drawn = arr.slice(0, Math.min(count, arr.length));
  return drawn.map((c) => ({
    ...c,
    orientation: Math.random() < 0.25 ? "reversed" : "upright",
  }));
}

// Re-export DrawnCard for convenience
import type { DrawnCard } from "@/types";