import { invoke } from '@tauri-apps/api/core';

// Состояние
let state = {
  guardianState: 'unknown',
  nodeId: '—',
  uptime: '—',
  peers: '—',
  chunks: '—',
  epoch: '—',
  tor: '—',
  monitorEnabled: false,
};

// Элементы DOM
const els = {
  state: document.getElementById('guardian-state'),
  nodeId: document.getElementById('guardian-node-id'),
  uptime: document.getElementById('guardian-uptime'),
  peers: document.getElementById('guardian-peers'),
  chunks: document.getElementById('guardian-chunks'),
  epoch: document.getElementById('guardian-epoch'),
  tor: document.getElementById('guardian-tor'),
  tg: document.getElementById('guardian-tg'),
  btnStart: document.getElementById('btn-start'),
  btnRestart: document.getElementById('btn-restart'),
  btnStop: document.getElementById('btn-stop'),
  btnToggle: document.getElementById('btn-toggle-monitor'),
  btnHealth: document.getElementById('btn-health'),
  btnTgTest: document.getElementById('btn-tg-test'),
  stageLog: document.getElementById('guardian-stage-log'),
};

// Лог этапов
function addStageLog(message, type = 'info') {
  const div = document.createElement('div');
  div.className = `log-entry log-${type}`;
  const now = new Date().toLocaleTimeString('ru-RU');
  div.textContent = `[${now}] ${message}`;
  els.stageLog.prepend(div);
  // Ограничиваем количество записей
  while (els.stageLog.children.length > 100) {
    els.stageLog.lastChild.remove();
  }
}

// Обновление интерфейса
let lastOk = null; // null=нет данных, true=связь есть, false=была потеряна
function updateUI() {
  els.state.textContent = state.guardianState;
  els.nodeId.textContent = state.nodeId;
  els.uptime.textContent = state.uptime;
  els.peers.textContent = state.peers;
  els.chunks.textContent = state.chunks;
  els.epoch.textContent = state.epoch;
  els.tor.textContent = state.tor;
  els.tg.textContent = state.monitorEnabled ? 'Активно' : 'Не настроено';

  // Цвет состояния
  els.state.className = 'guardian-stat-value';
  if (state.guardianState === 'Running') {
    els.state.classList.add('status-running');
  } else if (state.guardianState === 'Unhealthy') {
    els.state.classList.add('status-unhealthy');
  } else if (state.guardianState === 'Starting' || state.guardianState === 'Restarting') {
    els.state.classList.add('status-starting');
  }

  els.btnToggle.textContent = state.monitorEnabled ? '📊 Мониторинг: ВКЛ' : '📊 Мониторинг: ВЫКЛ';
  els.btnToggle.className = `btn btn-${state.monitorEnabled ? 'outline' : 'primary'}`;
}

// Запрос статуса
async function fetchStatus() {
  try {
    const result = await invoke('guardian_status_cmd');
    state.guardianState = result.state || 'unknown';
    state.monitorEnabled = result.monitor_enabled || false;

    const nodeStatus = result.node_status;
    if (nodeStatus) {
      state.nodeId = nodeStatus.node_id || '—';
      const uptimeMs = nodeStatus.uptime_ms || 0;
      state.uptime = Math.floor(uptimeMs / 60000) + ' мин';
      state.peers = String(nodeStatus.peers || 0);
      state.chunks = String(nodeStatus.chunks || 0);
      state.epoch = String(nodeStatus.epoch || 0);
      state.tor = nodeStatus.tor || '—';
    }

    updateUI();
    if (lastOk !== true) {
      if (lastOk === false) {
        addStageLog('✅ Связь с нодой восстановлена', 'success');
      }
      lastOk = true;
    }
  } catch (e) {
    if (lastOk !== false) {
      lastOk = false;
    }
    addStageLog(`Ошибка получения статуса: ${e}`, 'error');
  }
}

// Запуск ноды
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

// Перезапуск ноды
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

// Остановить ноду
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

// Переключить мониторинг
async function toggleMonitor() {
  addStageLog(state.monitorEnabled ? 'Выключение мониторинга...' : 'Включение мониторинга...', 'info');
  try {
    await invoke('guardian_toggle_monitor_cmd');
    addStageLog(`Мониторинг ${state.monitorEnabled ? 'выключен' : 'включен'}`, 'success');
    await fetchStatus();
  } catch (e) {
    addStageLog(`Ошибка переключения: ${e}`, 'error');
  }
}

// Проверить здоровье
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

// Тест Telegram
async function testTelegram() {
  addStageLog('Отправка тестового сообщения в Telegram...', 'info');
  try {
    await invoke('tg_send_test_cmd');
    addStageLog('Тестовое сообщение отправлено в Telegram', 'success');
  } catch (e) {
    addStageLog(`Ошибка Telegram: ${e}`, 'error');
  }
}

// Инициализация
async function init() {
  addStageLog('Гардиан инициализирован. Окно скрыто в трей.', 'info');
  await fetchStatus();
  setInterval(fetchStatus, 10000);
}

// Обработчики кнопок
els.btnStart.addEventListener('click', startNode);
els.btnRestart.addEventListener('click', restartNode);
els.btnStop.addEventListener('click', stopNode);
els.btnToggle.addEventListener('click', toggleMonitor);
els.btnHealth.addEventListener('click', checkHealth);
els.btnTgTest.addEventListener('click', testTelegram);

init();
