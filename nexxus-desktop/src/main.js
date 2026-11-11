import { invoke } from '@tauri-apps/api/core';
import { render as renderOverview } from './views/overview.js';
import { formatUptime, formatBytes } from './format.js';

// Состояние (flat, чтобы view-модули читали одно и то же)
let state = {
  guardianState: 'unknown',
  nodeId: '—',
  uptimeMs: 0,
  peers: '—',
  chunks: '—',
  epoch: '—',
  tor: '—',
  apiReachable: false,
  monitorEnabled: false,
  tgConfigured: false,
};

// Элементы DOM
const els = {
  btnStart: document.getElementById('btn-start'),
  btnRestart: document.getElementById('btn-restart'),
  btnStop: document.getElementById('btn-stop'),
  btnToggle: document.getElementById('btn-toggle-monitor'),
  btnHealth: document.getElementById('btn-health'),
  btnTgTest: document.getElementById('btn-tg-test'),
  stageLog: document.getElementById('guardian-stage-log'),
};

// --- Роутер вкладок ---
const TABS = ['overview', 'node', 'network', 'storage', 'logs', 'tor', 'epoch', 'settings'];
let activeTab = 'overview';
let logsLive = false;
let logsTimer = null;

function activateTab(name) {
  if (!TABS.includes(name)) name = 'overview';
  activeTab = name;
  document.querySelectorAll('.tab-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  document.querySelectorAll('.tab-pane').forEach((p) => {
    p.classList.toggle('active', p.id === `pane-${name}`);
  });
  refreshActivePane();
}

document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

// Лог этапов
function addStageLog(message, type = 'info') {
  const div = document.createElement('div');
  div.className = `log-entry log-${type}`;
  const now = new Date().toLocaleTimeString('ru-RU');
  div.textContent = `[${now}] ${message}`;
  els.stageLog.prepend(div);
  while (els.stageLog.children.length > 100) {
    els.stageLog.lastChild.remove();
  }
}

// --- Общие помощники ---
const $ = (id) => document.getElementById(id);

function setBox(id, text, cls = '') {
  const el = $(id);
  if (!el) return;
  el.innerHTML = '';
  if (typeof text === 'string') {
    el.textContent = text;
    if (cls) el.className = cls;
    return;
  }
  for (const [k, v] of Object.entries(text)) {
    const row = document.createElement('div');
    const key = document.createElement('span');
    key.className = 'k';
    key.textContent = `${k}: `;
    const val = document.createElement('span');
    val.className = 'v';
    val.textContent = typeof v === 'object' ? JSON.stringify(v) : String(v);
    row.appendChild(key);
    row.appendChild(val);
    el.appendChild(row);
  }
}

/// Прокси к локальному API ноды (авторизация токеном — внутри монитора).
async function api(method, params = null) {
  return invoke('node_api_cmd', { method, params });
}

/// Выполнить действие с записью результата в лог этапов.
async function action(label, fn) {
  try {
    const r = await fn();
    addStageLog(`${label}: ок`, 'success');
    return r;
  } catch (e) {
    addStageLog(`${label}: ошибка — ${e}`, 'error');
    return null;
  }
}

// Обновление интерфейса: overview-панель рендерит view-модуль
function updateUI() {
  renderOverview(document, state);
}

// Запрос статуса
let lastOk = null;
async function fetchStatus() {
  try {
    const result = await invoke('guardian_status_cmd');
    state.guardianState = result.state || 'unknown';
    state.monitorEnabled = result.monitor_enabled || false;
    state.tgConfigured = !!result.tg_configured;

    const nodeStatus = result.node_status;
    if (nodeStatus) {
      state.nodeId = nodeStatus.node_id || '—';
      state.uptimeMs = nodeStatus.uptime_ms || 0;
      state.peers = String(nodeStatus.peer_count ?? nodeStatus.peers ?? 0);
      state.apiReachable = !!nodeStatus.api_reachable;
      state.tor = nodeStatus.tor_enabled ? 'включён' : 'выключен';
    }
    updateUI();
    if (lastOk !== true) {
      if (lastOk === false) addStageLog('✅ Связь с нодой восстановлена', 'success');
      lastOk = true;
    }
    // Дополнительные метрики хранилища/эпохи — отдельными вызовами API.
    api('node_chunks').then((c) => {
      if (c && c.total_chunks !== undefined) {
        state.chunks = `${c.total_chunks} (${formatBytes(c.used_bytes || 0)})`;
        updateUI();
      }
    }).catch(() => {});
    api('node_epoch').then((e) => {
      if (e && e.epoch !== undefined) {
        state.epoch = String(e.epoch);
        updateUI();
      }
    }).catch(() => {});
  } catch (e) {
    if (lastOk !== false) {
      lastOk = false;
      state.apiReachable = false;
      updateUI();
    }
    addStageLog(`Ошибка получения статуса: ${e}`, 'error');
  }
}

// --- Обзор: кнопки гардиана ---
async function startNode() {
  addStageLog('Запуск nexxusd...', 'info');
  try {
    const result = await invoke('guardian_start_node_cmd');
    addStageLog(`nexxusd запущен: ${result.node_id || 'OK'}`, 'success');
    await fetchStatus();
  } catch (e) {
    addStageLog(`Ошибка запуска: ${e}`, 'error');
  }
}

async function restartNode() {
  addStageLog('Перезапуск nexxusd...', 'info');
  try {
    const result = await invoke('guardian_restart_node_cmd');
    addStageLog(`nexxusd перезапущен: ${result.node_id || 'OK'}`, 'success');
    await fetchStatus();
  } catch (e) {
    addStageLog(`Ошибка перезапуска: ${e}`, 'error');
  }
}

async function stopNode() {
  addStageLog('Остановка ноды...', 'info');
  try {
    await invoke('guardian_stop_node_cmd');
    addStageLog('Нода остановлена (процесс выгружен)', 'success');
    await fetchStatus();
  } catch (e) {
    addStageLog(`Ошибка остановки: ${e}`, 'error');
  }
}

async function toggleMonitor() {
  addStageLog(state.monitorEnabled ? 'Выключение мониторинга...' : 'Включение мониторинга...', 'info');
  try {
    await invoke('guardian_toggle_monitor_cmd');
    addStageLog('Режим мониторинга переключён', 'success');
    await fetchStatus();
  } catch (e) {
    addStageLog(`Ошибка переключения: ${e}`, 'error');
  }
}

async function checkHealth() {
  addStageLog('Проверка здоровья ноды...', 'info');
  try {
    await invoke('guardian_check_health_cmd');
    addStageLog('Проверка здоровья выполнена', 'success');
    await fetchStatus();
  } catch (e) {
    addStageLog(`Ошибка проверки: ${e}`, 'error');
  }
}

async function testTelegram() {
  addStageLog('Отправка тестового сообщения в Telegram...', 'info');
  try {
    await invoke('tg_send_test_cmd');
    addStageLog('Тестовое сообщение отправлено в Telegram', 'success');
  } catch (e) {
    addStageLog(`Ошибка Telegram: ${e}`, 'error');
  }
}

async function copyNodeId() {
  try {
    await navigator.clipboard.writeText(state.nodeId);
    addStageLog('Node ID скопирован в буфер обмена', 'success');
  } catch (e) {
    addStageLog(`Не удалось скопировать: ${e}`, 'error');
  }
}

// --- Панель «Нода»: конфиг ---
function readConfigForm() {
  const auditors = ($('cfg-auditors').value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return {
    listen: $('cfg-listen').value.trim(),
    api: $('cfg-api').value.trim(),
    auditors,
    threshold: Number($('cfg-threshold').value || 0),
    epoch_secs: Number($('cfg-epoch-secs').value || 300),
    tor: $('cfg-tor').checked,
    spec_version: $('cfg-spec-version').value.trim(),
    log_path: $('cfg-log-path').value.trim(),
  };
}

function fillConfigForm(cfg) {
  $('cfg-listen').value = cfg.listen ?? '';
  $('cfg-api').value = cfg.api ?? '';
  $('cfg-threshold').value = cfg.threshold ?? 0;
  $('cfg-epoch-secs').value = cfg.epoch_secs ?? 300;
  $('cfg-spec-version').value = cfg.spec_version ?? '';
  $('cfg-log-path').value = cfg.log_path ?? '';
  $('cfg-auditors').value = (cfg.auditors || []).join(', ');
  $('cfg-tor').checked = !!cfg.tor;
}

async function loadConfig() {
  const cfg = await action('Загрузка конфига', () => invoke('node_config_get_cmd'));
  if (cfg) {
    fillConfigForm(cfg);
    setBox('install-status', '');
  }
}

async function validateConfig() {
  const cfg = readConfigForm();
  const r = await action('Проверка конфига', () => invoke('node_config_validate_cmd', { cfg }));
  if (r) setBox('install-status', { 'валидность': 'ок', 'конфиг': cfg });
}

async function saveConfig() {
  const cfg = readConfigForm();
  const r = await action('Сохранение конфига', () => invoke('node_config_set_cmd', { cfg }));
  if (r) setBox('install-status', { 'статус': 'сохранено', 'требуется': 'перезапуск ноды' });
}

async function refreshInstallStatus() {
  try {
    const s = await invoke('node_install_status_cmd');
    setBox('install-status', {
      'юнит ноды установлен': s.installed ? 'да' : 'нет',
      'путь юнита': s.unit_path,
      'состояние юнита ноды': s.unit_state,
      'состояние юнита монитора': s.monitor_unit_state,
    });
  } catch (e) {
    setBox('install-status', `не удалось прочитать статус: ${e}`);
  }
}

async function installUnit() {
  const r = await action('Установка systemd-юнита ноды', () => invoke('node_install_cmd'));
  if (r) await refreshInstallStatus();
}

async function uninstallUnit() {
  const r = await action('Удаление systemd-юнита ноды', () => invoke('node_uninstall_cmd'));
  if (r) await refreshInstallStatus();
}

async function fullShutdown() {
  addStageLog('Полное отключение: нода останавливается, отчёт уходит в Telegram...', 'info');
  try {
    await invoke('guardian_shutdown_cmd');
    addStageLog('Полное отключение выполнено, монитор завершается', 'success');
  } catch (e) {
    addStageLog(`Ошибка полного отключения: ${e}`, 'error');
  }
}

// --- Панель «Сеть» ---
async function refreshPeers() {
  try {
    const p = await api('node_peers');
    const list = Array.isArray(p) ? p : (p.peers || []);
    if (!list.length) {
      setBox('peers-list', 'Пиров нет (пустой routing table)');
      return;
    }
    setBox('peers-list', list.map((x) => ({
      addr: x.addr || x.address || '—',
      node_id: (x.node_id || '').slice(0, 16) || '—',
      connected: x.connected ?? '—',
    })));
  } catch (e) {
    setBox('peers-list', `ошибка: ${e}`);
  }
}

async function pauseNode() {
  const r = await action('Пауза сети', () => api('node_pause'));
  if (r) refreshPeers();
}

async function resumeNode() {
  const r = await action('Возобновление сети', () => api('node_resume'));
  if (r) refreshPeers();
}

async function connectPeer() {
  const addr = ($('input-connect').value || '').trim();
  if (!addr) {
    addStageLog('Укажите адрес пира', 'error');
    return;
  }
  const r = await action(`Подключение к ${addr}`, () => api('node_connect', { addr }));
  if (r) {
    setBox('peers-list', r);
    refreshPeers();
  }
}

// --- Панель «Хранилище» ---
async function refreshChunks() {
  try {
    const c = await api('node_chunks');
    setBox('storage-data', {
      'всего чанков': c.total_chunks ?? '—',
      'размер чанка': c.chunk_size_bytes ? formatBytes(c.chunk_size_bytes) : '—',
      'занято': formatBytes(c.used_bytes || 0),
      'свободно': c.free_gb !== undefined ? `${c.free_gb} ГБ` : '—',
    });
  } catch (e) {
    setBox('storage-data', `ошибка: ${e}`);
  }
}

async function refreshSmp() {
  try {
    const s = await api('node_smp');
    const msgs = s.messages || [];
    if (!msgs.length) {
      setBox('storage-data', 'SMP-сообщений пока нет');
      return;
    }
    setBox('storage-data', msgs.slice(-20));
  } catch (e) {
    setBox('storage-data', `ошибка: ${e}`);
  }
}

async function runPor() {
  try {
    const r = await api('node_por');
    setBox('storage-data', r);
    addStageLog('PoR-проверка завершена', 'success');
  } catch (e) {
    setBox('storage-data', `ошибка: ${e}`);
    addStageLog(`PoR-проверка: ${e}`, 'error');
  }
}

async function storeInfo() {
  try {
    const s = await api('node_status');
    const cfg = await invoke('node_config_get_cmd');
    setBox('storage-data', {
      'node_id': s.node_id,
      'версия': s.version,
      'listen': s.listen_addr,
      'bound': s.bound_addr || '—',
      'аптайм': formatUptime(s.uptime_ms || 0),
      'paused': s.paused ? 'да' : 'нет',
      'store': '/home/thomas/.nexxus/store.redb',
      'log': cfg.log_path,
    });
  } catch (e) {
    setBox('storage-data', `ошибка: ${e}`);
  }
}

// --- Панель «Логи» ---
async function refreshLogs() {
  try {
    const r = await invoke('node_log_tail_cmd', { lines: 200 });
    $('logs-box').textContent = (r.lines || []).join('\n') || 'лог пуст';
    $('logs-box').scrollTop = $('logs-box').scrollHeight;
  } catch (e) {
    $('logs-box').textContent = `ошибка чтения лога: ${e}`;
  }
}

function toggleLogsLive() {
  logsLive = !logsLive;
  const btn = $('btn-logs-live');
  if (btn) btn.textContent = logsLive ? '📡 Авто: ВКЛ' : '📡 Авто: ВЫКЛ';
  if (logsTimer) {
    clearInterval(logsTimer);
    logsTimer = null;
  }
  if (logsLive) {
    refreshLogs();
    logsTimer = setInterval(refreshLogs, 5000);
  }
}

// --- Панель «Tor» ---
async function refreshTor() {
  try {
    const t = await api('node_tor');
    setBox('tor-data', {
      'включён': t.enabled ? 'да' : 'нет',
      'подключён': t.connected ? 'да' : 'нет',
      'onion': t.onion_address || '—',
      'socks': t.socks_port || t.socks_proxy || '—',
      'путь': t.path || '—',
    });
  } catch (e) {
    setBox('tor-data', `ошибка: ${e}`);
  }
}

async function dialOnion() {
  const addr = ($('input-onion').value || '').trim();
  if (!addr) {
    addStageLog('Укажите onion-адрес', 'error');
    return;
  }
  const r = await action(`Dial ${addr}`, () => api('node_dial_onion', { addr }));
  if (r) setBox('tor-data', r);
}

// --- Панель «Эпоха» ---
async function refreshEpoch() {
  try {
    const e = await api('node_epoch');
    setBox('epoch-data', {
      'эпоха': e.epoch ?? '—',
      'начало': e.started_at ?? e.start ?? '—',
      'конец': e.ends_at ?? e.end ?? '—',
      'merkle root': e.merkle_root || e.root || '—',
      'осталось сек': e.remaining_secs ?? e.remaining ?? '—',
    });
  } catch (err) {
    setBox('epoch-data', `ошибка: ${err}`);
  }
}

// --- Панель «Настройки»: Telegram ---
async function refreshTgStatus() {
  try {
    const st = await invoke('tg_config_status_cmd');
    setBox('tg-status', {
      'настроен': st.configured ? 'да ✅' : 'нет',
      'токен': `${st.token_set ? 'задан' : 'нет'} (источник: ${st.token_source})`,
      'chat_id': `${st.chat_set ? 'задан' : 'нет'} (источник: ${st.chat_source})`,
      'файл конфига': st.config_path,
    });
  } catch (e) {
    setBox('tg-status', `ошибка статуса: ${e}`);
  }
}

async function tgCheck() {
  const token = ($('tg-token').value || '').trim();
  if (!token) {
    addStageLog('Сначала вставьте токен', 'error');
    return;
  }
  const r = await action('Проверка токена (getMe)', () => invoke('tg_config_check_cmd', { botToken: token }));
  if (r) setBox('tg-status', { 'getMe': r.username ? `@${r.username} (id ${r.id})` : JSON.stringify(r) });
}

async function tgSave() {
  const token = ($('tg-token').value || '').trim();
  const chat = ($('tg-chat').value || '').trim();
  if (!token || !chat) {
    addStageLog('Нужны и токен, и chat_id', 'error');
    return;
  }
  const r = await action('Сохранение конфига Telegram', () =>
    invoke('tg_config_save_cmd', { botToken: token, chatId: chat }));
  if (r) {
    $('tg-token').value = '';
    $('tg-chat').value = '';
    setBox('tg-status', {
      'сохранено': 'да ✅',
      'бот': r.bot && r.bot.username ? `@${r.bot.username}` : '—',
      'источник': r.token_source,
    });
    await fetchStatus();
  }
}

// --- Автообновление активной панели ---
function refreshActivePane() {
  switch (activeTab) {
    case 'node':
      loadConfig();
      refreshInstallStatus();
      break;
    case 'network':
      refreshPeers();
      break;
    case 'storage':
      refreshChunks();
      break;
    case 'logs':
      refreshLogs();
      break;
    case 'tor':
      refreshTor();
      break;
    case 'epoch':
      refreshEpoch();
      break;
    case 'settings':
      refreshTgStatus();
      refreshIdentity();
      refreshVault();
      break;
    default:
      break;
  }
}

// --- Онбординг (Phase C1): индикатор текущего шага в шапке ---
const STEP_LABELS = {
  welcome: 'Приветствие',
  identity: 'Идентичность',
  store: 'Хранилище',
  network: 'Сеть',
  notifications: 'Уведомления',
  done: 'Готово',
};

async function fetchOnboarding() {
  try {
    const ob = await invoke('onboarding_get_cmd');
    const el = $('onboarding-hint');
    if (el && ob) {
      const cur = STEP_LABELS[ob.current] || ob.current;
      el.textContent = ob.current === 'done'
        ? 'Онбординг: пройден ✅'
        : `Онбординг: шаг «${cur}» (${(ob.completed || []).length}/5)`;
    }
  } catch (e) {
    const el = $('onboarding-hint');
    if (el) el.textContent = `Онбординг: ошибка — ${e}`;
  }
}

// --- Инициализация ---
async function init() {
  activateTab('overview');
  addStageLog('Гардиан инициализирован.', 'info');
  await fetchStatus();
  await fetchOnboarding();
  setInterval(fetchStatus, 5000);
  setInterval(fetchOnboarding, 30000);
}

// Обработчики кнопок
els.btnStart.addEventListener('click', startNode);
els.btnRestart.addEventListener('click', restartNode);
els.btnStop.addEventListener('click', stopNode);
els.btnToggle.addEventListener('click', toggleMonitor);
els.btnHealth.addEventListener('click', checkHealth);
els.btnTgTest.addEventListener('click', testTelegram);
$('btn-copy-node-id').addEventListener('click', copyNodeId);

$('btn-cfg-load').addEventListener('click', loadConfig);
$('btn-cfg-validate').addEventListener('click', validateConfig);
$('btn-cfg-save').addEventListener('click', saveConfig);
$('btn-unit-install').addEventListener('click', installUnit);
$('btn-unit-uninstall').addEventListener('click', uninstallUnit);
$('btn-full-shutdown').addEventListener('click', fullShutdown);

$('btn-peers-refresh').addEventListener('click', refreshPeers);
$('btn-pause').addEventListener('click', pauseNode);
$('btn-resume').addEventListener('click', resumeNode);
$('btn-connect').addEventListener('click', connectPeer);

$('btn-chunks-refresh').addEventListener('click', refreshChunks);
$('btn-smp-refresh').addEventListener('click', refreshSmp);
$('btn-por').addEventListener('click', runPor);
$('btn-store-info').addEventListener('click', storeInfo);

$('btn-logs-refresh').addEventListener('click', refreshLogs);
$('btn-logs-live').addEventListener('click', toggleLogsLive);
$('btn-logs-clear').addEventListener('click', () => { $('logs-box').textContent = ''; });

$('btn-tor-refresh').addEventListener('click', refreshTor);
$('btn-dial-onion').addEventListener('click', dialOnion);

$('btn-epoch-refresh').addEventListener('click', refreshEpoch);

$('btn-tg-check').addEventListener('click', tgCheck);
$('btn-tg-save').addEventListener('click', tgSave);
$('btn-tg-test2').addEventListener('click', testTelegram);

// --- Идентичность (BIP39): статус / экспорт / импорт сид-фразы ---
async function refreshIdentity() {
  try {
    const st = await api('node_identity_status');
    $('id-status').textContent = st.initialized
      ? `Идентичность создана: ${st.word_count} слов, node_id ${st.node_id.slice(0, 16)}…`
      : 'Идентичность ещё не создана';
  } catch (e) {
    $('id-status').textContent = `Ошибка: ${e}`;
  }
}

async function exportSeed() {
  if (!confirm('Показать сид-фразу на экране? Убедитесь, что никто не подглядывает. Фраза не попадёт в логи.')) return;
  try {
    const r = await api('node_identity_export', { confirm: true });
    const box = $('id-export-box');
    box.textContent = r.mnemonic;
    box.classList.remove('hidden');
    $('btn-id-copy').disabled = false;
    addStageLog(`Сид-фраза показана (${r.word_count} слов)`, 'success');
  } catch (e) {
    addStageLog(`Экспорт сида отклонён: ${e}`, 'error');
  }
}

async function copySeed() {
  const box = $('id-export-box');
  if (!box.textContent) return;
  try {
    await navigator.clipboard.writeText(box.textContent);
    addStageLog('Сид-фраза скопирована в буфер обмена', 'success');
  } catch (e) {
    addStageLog(`Буфер обмена недоступен: ${e}`, 'error');
  }
}

async function importSeed() {
  const phrase = ($('id-import').value || '').trim();
  if (!phrase) { $('id-import-result').textContent = 'Введите сид-фразу.'; return; }
  if (!confirm('Восстановить идентичность из этой сид-фразы? На уже инициализированном узле с другим сидом операция будет отклонена.')) return;
  try {
    const r = await api('node_identity_import', { mnemonic: phrase });
    $('id-import-result').textContent = `Статус: ${r.status}, node_id: ${r.node_id.slice(0, 16)}…`;
    addStageLog(`Импорт сида: ${r.status}`, r.status === 'already' ? 'success' : 'success');
    await refreshIdentity();
  } catch (e) {
    $('id-import-result').textContent = `Отклонено: ${e}`;
    addStageLog(`Импорт сида отклонён: ${e}`, 'error');
  }
}

$('btn-id-refresh').addEventListener('click', refreshIdentity);
$('btn-id-export').addEventListener('click', exportSeed);
$('btn-id-copy').addEventListener('click', copySeed);
$('btn-id-import').addEventListener('click', importSeed);

// --- Бэкап сида (R2): seed.vault ---
async function refreshVault() {
  try {
    const st = await api('node_seed_vault_status');
    $('vault-status').textContent = st.exists
      ? `Бэкап есть: ${st.path} (создан ${new Date(st.created_at * 1000).toLocaleString('ru-RU')}, duress-PIN: ${st.has_duress_pin ? 'да' : 'нет'}, kdf ${st.kdf_rounds})`
      : 'Бэкап ещё не создан';
  } catch (e) {
    $('vault-status').textContent = `Ошибка: ${e}`;
  }
}

async function vaultBackup() {
  const pin = ($('vault-pin').value || '').trim();
  if (pin.length < 4) { $('vault-result').textContent = 'PIN минимум 4 символа.'; return; }
  const duress = ($('vault-duress').value || '').trim() || null;
  try {
    const r = await api('node_seed_backup', { pin, duress_pin: duress });
    $('vault-result').textContent = `Бэкап создан: ${r.path}`;
    addStageLog('seed.vault создан (зашифрован)', 'success');
    $('vault-pin').value = ''; $('vault-duress').value = '';
    await refreshVault();
  } catch (e) {
    $('vault-result').textContent = `Ошибка: ${e}`;
    addStageLog(`Бэкап сида отклонён: ${e}`, 'error');
  }
}

async function vaultRestore() {
  const pin = ($('vault-restore-pin').value || '').trim();
  if (!pin) { $('vault-result').textContent = 'Введите PIN.'; return; }
  try {
    const r = await api('node_seed_restore', { pin });
    if (r.status === 'duress') {
      $('vault-result').textContent = '⚠️ Введён duress-PIN: алерт отправлен, сид НЕ восстановлен.';
      addStageLog('⚠️ DURESS-PIN в seed.vault — алерт!', 'error');
      try { await invoke('tg_send_alert_cmd', { text: '⚠️ NeXXus: введён duress-PIN seed.vault — возможное принуждение!' }); } catch (_) {}
    } else {
      $('vault-result').textContent = `Статус: ${r.status}${r.node_id ? `, node_id ${r.node_id.slice(0, 16)}…` : ''}`;
      addStageLog(`Восстановление seed.vault: ${r.status}`, r.status === 'wrong_pin' ? 'error' : 'success');
    }
    $('vault-restore-pin').value = '';
  } catch (e) {
    $('vault-result').textContent = `Ошибка: ${e}`;
    addStageLog(`Восстановление отклонено: ${e}`, 'error');
  }
}

$('btn-vault-refresh').addEventListener('click', refreshVault);
$('btn-vault-backup').addEventListener('click', vaultBackup);
$('btn-vault-restore').addEventListener('click', vaultRestore);

init();
