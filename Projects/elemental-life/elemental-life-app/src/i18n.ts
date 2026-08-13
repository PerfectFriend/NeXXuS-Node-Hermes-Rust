// i18n.ts - Localization system
// Supported locales and translations

export type Locale = 'en' | 'ru' | 'es' | 'de' | 'zh' | 'ja';

export interface Translations {
  loading: string;
  splashTitle: string;
  splashSubtitle: string;
  // App UI
  appTitle: string;
  sandbox: string;
  puzzle: string;
  presets: string;
  tuning: string;
  chart: string;
  rules: string;
  settings: string;
  wallet: string;
  geometry: string;
  seed: string;
  running: string;
  speed: string;
  droplets: string;
  level: string;
  retry: string;
  newGame: string;
  step: string;
  zoomIn: string;
  zoomOut: string;
  resetView: string;
  centerView: string;
  brush: string;
  // Elements
  elemEmpty: string;
  elemLife: string;
  elemFire: string;
  elemWater: string;
  elemEarth: string;
  elemSteam: string;
  // Puzzle
  puzzleWon: string;
  puzzleFailed: string;
  winStreak: string;
  nextLevel: string;
  // Settings
  language: string;
  fullscreen: string;
  theme: string;
  about: string;
  version: string;
}

const translations: Record<Locale, Translations> = {
  en: {
    loading: 'Loading...',
    splashTitle: 'Elemental Life',
    splashSubtitle: 'Cyberpunk Oasis',
    appTitle: 'Elemental Life',
    sandbox: 'Sandbox',
    puzzle: 'Puzzle',
    presets: 'Presets',
    tuning: 'Tuning',
    chart: 'Chart',
    rules: 'Rules',
    settings: 'Settings',
    wallet: 'Wallet',
    geometry: 'Geometry',
    seed: 'Seed',
    running: 'Running',
    speed: 'Speed',
    droplets: 'Droplets',
    level: 'Level',
    retry: 'Retry',
    newGame: 'New Game',
    step: 'Step',
    zoomIn: 'Zoom In',
    zoomOut: 'Zoom Out',
    resetView: 'Reset View',
    centerView: 'Center',
    brush: 'Brush',
    elemEmpty: 'Empty',
    elemLife: 'Life',
    elemFire: 'Fire',
    elemWater: 'Water',
    elemEarth: 'Earth',
    elemSteam: 'Steam',
    puzzleWon: 'Level Complete!',
    puzzleFailed: 'Failed',
    winStreak: 'Win Streak',
    nextLevel: 'Next Level',
    language: 'Language',
    fullscreen: 'Fullscreen',
    theme: 'Theme',
    about: 'About',
    version: 'Version',
  },
  ru: {
    loading: 'Загрузка...',
    splashTitle: 'Элементарная Жизнь',
    splashSubtitle: 'Киберпанк Оазис',
    appTitle: 'Элементарная Жизнь',
    sandbox: 'Песочница',
    puzzle: 'Головоломка',
    presets: 'Пресеты',
    tuning: 'Настройка',
    chart: 'График',
    rules: 'Правила',
    settings: 'Настройки',
    wallet: 'Кошелёк',
    geometry: 'Геометрия',
    seed: 'Сид',
    running: 'Работает',
    speed: 'Скорость',
    droplets: 'Капли',
    level: 'Уровень',
    retry: 'Повторить',
    newGame: 'Новая игра',
    step: 'Шаг',
    zoomIn: 'Приблизить',
    zoomOut: 'Отдалить',
    resetView: 'Сброс вида',
    centerView: 'Центр',
    brush: 'Кисть',
    elemEmpty: 'Пустота',
    elemLife: 'Жизнь',
    elemFire: 'Огонь',
    elemWater: 'Вода',
    elemEarth: 'Земля',
    elemSteam: 'Пар',
    puzzleWon: 'Уровень пройден!',
    puzzleFailed: 'Не пройден',
    winStreak: 'Серия побед',
    nextLevel: 'Следующий уровень',
    language: 'Язык',
    fullscreen: 'Полный экран',
    theme: 'Тема',
    about: 'О программе',
    version: 'Версия',
  },
  es: {
    loading: 'Cargando...',
    splashTitle: 'Vida Elemental',
    splashSubtitle: 'Oasis Cyberpunk',
    appTitle: 'Vida Elemental',
    sandbox: 'Caja de arena',
    puzzle: 'Puzle',
    presets: 'Preajustes',
    tuning: 'Ajustes',
    chart: 'Gráfico',
    rules: 'Reglas',
    settings: 'Configuración',
    wallet: 'Cartera',
    geometry: 'Geometría',
    seed: 'Semilla',
    running: 'Ejecutando',
    speed: 'Velocidad',
    droplets: 'Gotitas',
    level: 'Nivel',
    retry: 'Reintentar',
    newGame: 'Nuevo juego',
    step: 'Paso',
    zoomIn: 'Acercar',
    zoomOut: 'Alejar',
    resetView: 'Restablecer vista',
    centerView: 'Centrar',
    brush: 'Pincel',
    elemEmpty: 'Vacío',
    elemLife: 'Vida',
    elemFire: 'Fuego',
    elemWater: 'Agua',
    elemEarth: 'Tierra',
    elemSteam: 'Vapor',
    puzzleWon: '¡Nivel completado!',
    puzzleFailed: 'Fallado',
    winStreak: 'Racha de victorias',
    nextLevel: 'Siguiente nivel',
    language: 'Idioma',
    fullscreen: 'Pantalla completa',
    theme: 'Tema',
    about: 'Acerca de',
    version: 'Versión',
  },
  de: {
    loading: 'Laden...',
    splashTitle: 'Elementares Leben',
    splashSubtitle: 'Cyberpunk Oase',
    appTitle: 'Elementares Leben',
    sandbox: 'Sandbox',
    puzzle: 'Rätsel',
    presets: 'Voreinstellungen',
    tuning: 'Einstellungen',
    chart: 'Diagramm',
    rules: 'Regeln',
    settings: 'Einstellungen',
    wallet: 'Brieftasche',
    geometry: 'Geometrie',
    seed: 'Seed',
    running: 'Läuft',
    speed: 'Geschwindigkeit',
    droplets: 'Tropfen',
    level: 'Level',
    retry: 'Wiederholen',
    newGame: 'Neues Spiel',
    step: 'Schritt',
    zoomIn: 'Vergrößern',
    zoomOut: 'Verkleinern',
    resetView: 'Ansicht zurücksetzen',
    centerView: 'Zentrieren',
    brush: 'Pinsel',
    elemEmpty: 'Leer',
    elemLife: 'Leben',
    elemFire: 'Feuer',
    elemWater: 'Wasser',
    elemEarth: 'Erde',
    elemSteam: 'Dampf',
    puzzleWon: 'Level abgeschlossen!',
    puzzleFailed: 'Fehlgeschlagen',
    winStreak: 'Gewinnserie',
    nextLevel: 'Nächstes Level',
    language: 'Sprache',
    fullscreen: 'Vollbild',
    theme: 'Thema',
    about: 'Über',
    version: 'Version',
  },
  zh: {
    loading: '加载中...',
    splashTitle: '元素生命',
    splashSubtitle: '赛博朋克绿洲',
    appTitle: '元素生命',
    sandbox: '沙盒',
    puzzle: '谜题',
    presets: '预设',
    tuning: '调节',
    chart: '图表',
    rules: '规则',
    settings: '设置',
    wallet: '钱包',
    geometry: '几何',
    seed: '种子',
    running: '运行中',
    speed: '速度',
    droplets: '水滴',
    level: '关卡',
    retry: '重试',
    newGame: '新游戏',
    step: '步骤',
    zoomIn: '放大',
    zoomOut: '缩小',
    resetView: '重置视图',
    centerView: '居中',
    brush: '画笔',
    elemEmpty: '空',
    elemLife: '生命',
    elemFire: '火',
    elemWater: '水',
    elemEarth: '土',
    elemSteam: '蒸汽',
    puzzleWon: '关卡完成!',
    puzzleFailed: '失败',
    winStreak: '连胜',
    nextLevel: '下一关',
    language: '语言',
    fullscreen: '全屏',
    theme: '主题',
    about: '关于',
    version: '版本',
  },
  ja: {
    loading: '読み込み中...',
    splashTitle: 'エレメンタル・ライフ',
    splashSubtitle: 'サイバーパンク・オアシス',
    appTitle: 'エレメンタル・ライフ',
    sandbox: 'サンドボックス',
    puzzle: 'パズル',
    presets: 'プリセット',
    tuning: '調整',
    chart: 'チャート',
    rules: 'ルール',
    settings: '設定',
    wallet: 'ウォレット',
    geometry: 'ジオメトリ',
    seed: 'シード',
    running: '実行中',
    speed: '速度',
    droplets: '水滴',
    level: 'レベル',
    retry: 'リトライ',
    newGame: '新しいゲーム',
    step: 'ステップ',
    zoomIn: 'ズームイン',
    zoomOut: 'ズームアウト',
    resetView: 'ビューをリセット',
    centerView: '中央',
    brush: 'ブラシ',
    elemEmpty: '空',
    elemLife: '命',
    elemFire: '火',
    elemWater: '水',
    elemEarth: '土',
    elemSteam: '蒸気',
    puzzleWon: 'レベルクリア!',
    puzzleFailed: '失敗',
    winStreak: '連勝',
    nextLevel: '次のレベル',
    language: '言語',
    fullscreen: 'フルスクリーン',
    theme: 'テーマ',
    about: 'このアプリについて',
    version: 'バージョン',
  },
};

let currentLocale: Locale = 'en';
let currentTranslations: Translations = translations.en;

export function getLocale(): Locale {
  return currentLocale;
}

export function getTranslations(): Translations {
  return currentTranslations;
}

export function setLocale(locale: Locale): void {
  if (translations[locale]) {
    currentLocale = locale;
    currentTranslations = translations[locale];
  }
}

export function detectSystemLocale(): Locale {
  if (typeof navigator !== 'undefined') {
    const lang = navigator.language.toLowerCase();
    const primaryLang = lang.split('-')[0] as Locale;
    if (translations[primaryLang]) {
      return primaryLang;
    }
    // Check full locale (e.g., zh-CN -> zh)
    for (const key of Object.keys(translations)) {
      if (lang.startsWith(key)) {
        return key as Locale;
      }
    }
  }
  return 'en';
}

export function initI18n(): void {
  const detected = detectSystemLocale();
  setLocale(detected);
}

export function t(key: keyof Translations): string {
  return currentTranslations[key] || translations.en[key] || key;
}