// Интерфейс узла NeXXus — десктоп-монитор с системным треем.
// Вызывает Tauri команды, которые проксируют JSON-RPC запросы к локальному API nexxusd (127.0.0.1:4010).
//
// Архитектура:
//   - Все данные из nexxusd получаются через Tauri `invoke()` команды.
//   - Команды на стороне Rust (src-tauri/main.rs) делают JSON-RPC запросы
//     к WebSocket серверу nexxusd на ws://127.0.0.1:4010.
//   - Если nexxusd не запущен, каждая команда вернёт ошибку "Connection refused",
//     которая отображается в логе приложения.

import { invoke } from '@tauri-apps/api/core';

// Базовый адрес WebSocket API (используется только для справки;
// реальные запросы идут через Tauri invoke).
const API_BASE = 'ws://127.0.0.1:4010';

// Интервал автообновления в миллисекундах (5 секунд).
let refreshInterval = null;
// Флаг включения/выключения автообновления.
let autoRefresh = true;

// ===== Ссылки на DOM элементы =====

// Индикаторы состояния в шапке
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const uptimeText = document.getElementById('uptime-text');
const peerCountText = document.getElementById('peer-count');
const chunkCountText = document.getElementById('chunk-count');
const smpCountText = document.getElementById('smp-count');
const epochText = document.getElementById('epoch-text');
const torText = document.getElementById('tor-text');

// Таблицы данных
const peersBody = document.getElementById('peers-body');
const chunksBody = document.getElementById('chunks-body');
const smpBody = document.getElementById('smp-body');
const logBody = document.getElementById('log-body');

// Форма отправки SMP
const smpForm = document.getElementById('smp-form');
const smpResult = document.getElementById('smp-result');

// ===== Вспомогательные функции =====

/// Добавляет запись в лог активности (в начало таблицы).
/// Ограничивает количество записей 50, удаляя старые.
function log(msg) {
  const now = new Date().toLocaleTimeString();
  const row = document.createElement('tr');
  row.innerHTML = `<td>${now}</td><td>${msg}</td>`;
  logBody.insertBefore(row, logBody.firstChild);
  if (logBody.children.length > 50) logBody.removeChild(logBody.lastChild);
}

/// Устанавливает визуальный статус подключения (онлайн/оффлайн).
function setStatus(connected) {
  if (connected) {
    statusDot.className = 'status-dot online';
    statusText.textContent = 'Онлайн';
  } else {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Оффлайн';
  }
}

/// Проверяет, что строка является корректным hex (только символы 0-9, a-f, A-F).
function isValidHex(str) {
  return /^[0-9a-fA-F]*$/.test(str);
}

/// Преобразует hex-строку в массив байт.
function hexToBytes(hex) {
  const bytes = [];
  for (let i = 0; i < hex.length; i += 2) {
    bytes.push(parseInt(hex.substr(i, 2), 16));
  }
  return bytes;
}

// ===== Функции получения данных =====

/// Запрашивает статус узла через Tauri команду `node_status`.
async function fetchNodeStatus() {
  try {
    const res = await invoke('node_status');
    const data = JSON.parse(res);
    setStatus(true);
    uptimeText.textContent = `${Math.floor(data.uptime_ms / 1000)} с`;
    log(`Статус узла: ${data.node_id.substring(0, 16)}...`);
    return data;
  } catch (e) {
    setStatus(false);
    const msg = e.message || e;
    log(`Ошибка статуса: ${msg}`);
    if (msg.includes('Connection refused')) {
      log('nexxusd не запущен! Запустите nexxusd перед использованием монитора.');
    }
    return null;
  }
}

/// Запрашивает список пиров через `node_peers`.
async function fetchPeers() {
  try {
    const res = await invoke('node_peers');
    const data = JSON.parse(res);
    const peers = data.peers || [];
    peerCountText.textContent = peers.length;
    peersBody.innerHTML = '';
    peers.forEach((p, i) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${i + 1}</td>
        <td>${p.node_id.substring(0, 16)}...</td>
        <td>${p.addr}</td>
        <td><span class="badge ${p.direction === 'inbound' ? 'in' : 'out'}">${p.direction}</span></td>
        <td>${new Date(p.connected_at * 1000).toLocaleTimeString()}</td>
      `;
      peersBody.appendChild(row);
    });
  } catch (e) {
    log(`Ошибка пиров: ${e.message || e}`);
  }
}

/// Запрашивает статистику чанков через `node_chunks`.
async function fetchChunks() {
  try {
    const res = await invoke('node_chunks');
    const data = JSON.parse(res);
    chunkCountText.textContent = data.total_chunks || 0;
    chunksBody.innerHTML = '';
    const row = document.createElement('tr');
    row.innerHTML = `
      <td colspan="4">Всего чанков: ${data.total_chunks || 0}, использовано байт: ${data.used_bytes || 0}</td>
    `;
    chunksBody.appendChild(row);
  } catch (e) {
    log(`Ошибка чанков: ${e.message || e}`);
  }
}

/// Запрашивает историю SMP через `node_smp`.
async function fetchSmp() {
  try {
    const res = await invoke('node_smp');
    const data = JSON.parse(res);
    const messages = data.messages || [];
    smpCountText.textContent = messages.length;
    smpBody.innerHTML = '';
    messages.slice().reverse().forEach((m) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${m.id}</td>
        <td><span class="badge ${m.direction === 'sent' ? 'sent' : 'recv'}">${m.direction}</span></td>
        <td>${m.recipient_node_id.substring(0, 16)}...</td>
        <td>${m.payload_size} Б</td>
        <td><span class="badge ${m.status}">${m.status}</span></td>
        <td>${new Date(m.timestamp * 1000).toLocaleTimeString()}</td>
      `;
      smpBody.appendChild(row);
    });
  } catch (e) {
    log(`Ошибка SMP: ${e.message || e}`);
  }
}

/// Запрашивает статус эпохи через `node_epoch`.
async function fetchEpoch() {
  try {
    const res = await invoke('node_epoch');
    const data = JSON.parse(res);
    epochText.textContent = `Эпоха ${data.epoch_number}, кворум: ${data.quorum_met ? 'да' : 'нет'}`;
  } catch (e) {
    log(`Ошибка эпохи: ${e.message || e}`);
  }
}

/// Запрашивает статус Tor через `node_tor`.
async function fetchTor() {
  try {
    const res = await invoke('node_tor');
    const data = JSON.parse(res);
    torText.textContent = data.enabled
      ? (data.connected ? `Tor активен (${data.onion_address || 'onion'})` : 'Tor включён, не подключён')
      : 'Tor выключен';
  } catch (e) {
    log(`Ошибка Tor: ${e.message || e}`);
  }
}

/// Обновляет все панели параллельно.
async function refreshAll() {
  await Promise.all([
    fetchNodeStatus(),
    fetchPeers(),
    fetchChunks(),
    fetchSmp(),
    fetchEpoch(),
    fetchTor(),
  ]);
}

/// Отправляет SMP envelope через форму.
async function sendSmpEnvelope(e) {
  e.preventDefault();
  const recipient = document.getElementById('smp-recipient').value.trim();
  const payloadHex = document.getElementById('smp-payload').value.trim();
  const addr = document.getElementById('smp-addr').value.trim() || '127.0.0.1:4001';

  // Валидация: поля не пустые
  if (!recipient || !payloadHex) {
    smpResult.textContent = 'Заполните все поля';
    smpResult.className = 'error';
    return;
  }

  // Валидация: recipient и payload должны быть корректным hex
  if (!isValidHex(recipient)) {
    smpResult.textContent = 'Node ID должен быть в формате hex (0-9, a-f)';
    smpResult.className = 'error';
    return;
  }
  if (!isValidHex(payloadHex)) {
    smpResult.textContent = 'Payload должен быть в формате hex (0-9, a-f)';
    smpResult.className = 'error';
    return;
  }
  // Валидация: чётная длина hex строки (байты)
  if (recipient.length % 2 !== 0) {
    smpResult.textContent = 'Node ID должен содержать чётное количество hex-символов';
    smpResult.className = 'error';
    return;
  }
  if (payloadHex.length % 2 !== 0) {
    smpResult.textContent = 'Payload должен содержать чётное количество hex-символов';
    smpResult.className = 'error';
    return;
  }

  try {
    const bytes = hexToBytes(payloadHex);
    const res = await invoke('send_smp_envelope', {
      recipient_node_id: recipient,
      payload: bytes,
      addr: addr,
    });
    const data = JSON.parse(res);
    smpResult.textContent = `Отправлено: ${data.envelope_id || 'OK'}`;
    smpResult.className = 'success';
    smpForm.reset();
    await fetchSmp();
  } catch (err) {
    smpResult.textContent = `Ошибка: ${err.message || err}`;
    smpResult.className = 'error';
  }
}

/// Поставить узел на паузу.
async function pauseNode() {
  try {
    await invoke('node_pause');
    log('Узел поставлен на паузу');
    await refreshAll();
  } catch (e) {
    log(`Ошибка паузы: ${e.message || e}`);
  }
}

/// Возобновить работу узла.
async function resumeNode() {
  try {
    await invoke('node_resume');
    log('Узел возобновлён');
    await refreshAll();
  } catch (e) {
    log(`Ошибка возобновления: ${e.message || e}`);
  }
}

// ===== Инициализация =====

document.addEventListener('DOMContentLoaded', () => {
  smpForm.addEventListener('submit', sendSmpEnvelope);

  document.getElementById('btn-pause').addEventListener('click', pauseNode);
  document.getElementById('btn-resume').addEventListener('click', resumeNode);
  document.getElementById('btn-refresh').addEventListener('click', refreshAll);

  document.getElementById('toggle-autorefresh').addEventListener('click', (e) => {
    autoRefresh = !autoRefresh;
    e.target.textContent = autoRefresh ? 'Автообновление: ВКЛ' : 'Автообновление: ВЫКЛ';
    e.target.className = autoRefresh ? 'btn btn-success' : 'btn btn-warning';
    if (autoRefresh) startAutoRefresh();
    else stopAutoRefresh();
  });

  // Первичное обновление при загрузке
  refreshAll();
  startAutoRefresh();
});

function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(refreshAll, 5000);
}

function stopAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
}
