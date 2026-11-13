/* NeXXus Node Mobile — тонкий WS-клиент к локальному API nexxusd (JSON-RPC 2.0, auth token). */
let ws = null, msgId = 0;
const $ = (id) => document.getElementById(id);

function log(msg, cls) {
  const d = document.createElement('div');
  d.className = cls || '';
  d.textContent = `[${new Date().toLocaleTimeString('ru-RU')}] ${msg}`;
  $('log').prepend(d);
}

function out(obj) {
  $('out').textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 1).slice(0, 4000);
}

function call(method, params) {
  return new Promise((resolve, reject) => {
    if (!ws || ws.readyState !== 1) return reject('нет соединения');
    const id = ++msgId;
    const onMsg = (ev) => {
      const r = JSON.parse(ev.data);
      if (r.id !== id) return;
      ws.removeEventListener('message', onMsg);
      r.error ? reject(r.error.message || JSON.stringify(r.error)) : resolve(r.result);
    };
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({ jsonrpc: '2.0', method, params: params || null, id }));
    setTimeout(() => reject('timeout'), 6000);
  });
}

$('btn-connect').onclick = () => {
  const addr = $('addr').value.trim();
  const token = $('token').value.trim();
  if (!addr.startsWith('ws://')) return log('адрес должен начинаться с ws://', 'err');
  if (!token) return log('нужен API token', 'err');
  try { ws && ws.close(); } catch (e) {}
  log(`connect ${addr} …`);
  ws = new WebSocket(addr);
  ws.onopen = async () => {
    log('ws open, auth…', 'ok');
    try {
      await call('auth', { token });
      log('auth OK', 'ok');
      const s = await call('node_status');
      out(s);
    } catch (e) { log('auth failed: ' + e, 'err'); }
  };
  ws.onerror = () => log('ws error', 'err');
  ws.onclose = () => log('ws closed', 'err');
};

$('btn-status').onclick = async () => { try { out(await call('node_status')); } catch (e) { log(e, 'err'); } };
$('btn-peers').onclick = async () => { try { out(await call('node_peers')); } catch (e) { log(e, 'err'); } };
$('btn-chunks').onclick = async () => { try { out(await call('node_chunks')); } catch (e) { log(e, 'err'); } };
$('btn-smp').onclick = async () => {
  $('smp-card').style.display = $('smp-card').style.display === 'none' ? '' : 'none';
  try { out(await call('node_smp')); } catch (e) { log(e, 'err'); }
};
$('btn-smp-send').onclick = async () => {
  try {
    const r = await call('node_smp_send', {
      recipient_node_id: $('smp-rcpt').value.trim(),
      recipient_pub: $('smp-pub').value.trim(),
      message: $('smp-msg').value,
    });
    log('smp: ' + JSON.stringify(r), r.ok ? 'ok' : 'err');
    out(r);
  } catch (e) { log('smp: ' + e, 'err'); }
};

log('NeXXus Node Mobile готов. Введите адрес узла и токен.');
