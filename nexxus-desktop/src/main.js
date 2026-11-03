// Интерфейс узла NeXXus — десктоп-монитор с системным треем.
// Вызывает Tauri команды, которые проксируют JSON-RPC запросы к локальному API nexxusd (127.0.0.1:4010).

import { invoke } from '@tauri-apps/api/core';

const API_BASE = 'ws://127.0.0.1:4010';
let refreshInterval = null;
let autoRefresh = true;

// Индикаторы состояния
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const uptimeText = document.getElementById('uptime-text');
const peerCountText = document.getElementById('peer-count');
const chunkCountText = document.getElementById('chunk-count');
const smpCountText = document.getElementById('smp-count');
const epochText = document.getElementById('epoch-text');
const torText = document.getElementById('tor-text');

// Таблицы
const peersBody = document.getElementById('peers-body');
const chunksBody = document.getElementById('chunks-body');
const smpBody = document.getElementById('smp-body');
const logBody = document.getElementById('log-body');

// Форма отправки SMP
const smpForm = document.getElementById('smp-form');
const smpResult = document.getElementById('smp-result');

function log(msg) {
  const now = new Date().toLocaleTimeString();
  const row = document.createElement('tr');
  row.innerHTML = `<td>${now}</td><td>${msg}</td>`;
  logBody.insertBefore(row, logBody.firstChild);
  if (logBody.children.length > 50) logBody.removeChild(logBody.lastChild);
}

function setStatus(connected) {
  if (connected) {
    statusDot.className = 'status-dot online';
    statusText.textContent = 'Онлайн';
  } else {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Оффлайн';
  }
}

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
    log(`Ошибка статуса: ${e.message || e}`);
    return null;
  }
}

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

async function fetchEpoch() {
  try {
    const res = await invoke('node_epoch');
    const data = JSON.parse(res);
    epochText.textContent = `Эпоха ${data.epoch_number}, кворум: ${data.quorum_met ? 'да' : 'нет'}`;
  } catch (e) {
    log(`Ошибка эпохи: ${e.message || e}`);
  }
}

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

async function sendSmpEnvelope(e) {
  e.preventDefault();
  const recipient = document.getElementById('smp-recipient').value;
  const payloadHex = document.getElementById('smp-payload').value;
  const addr = document.getElementById('smp-addr').value || '127.0.0.1:4001';

  if (!recipient || !payloadHex) {
    smpResult.textContent = 'Заполните все поля';
    smpResult.className = 'error';
    return;
  }

  try {
    // Convert hex string to byte array
    const bytes = [];
    for (let i = 0; i < payloadHex.length; i += 2) {
      bytes.push(parseInt(payloadHex.substr(i, 2), 16));
    }

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

async function pauseNode() {
  try {
    await invoke('node_pause');
    log('Узел поставлен на паузу');
    await refreshAll();
  } catch (e) {
    log(`Ошибка паузы: ${e.message || e}`);
  }
}

async function resumeNode() {
  try {
    await invoke('node_resume');
    log('Узел возобновлён');
    await refreshAll();
  } catch (e) {
    log(`Ошибка возобновления: ${e.message || e}`);
  }
}

// Инициализация
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
