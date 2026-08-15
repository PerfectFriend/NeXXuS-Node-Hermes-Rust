// Telegram Bot — Elemental Life
// Запуск: node telegram.mjs
// Зависимости: только Node.js 18+ (native fetch), PowerShell для отправки файлов

import { execSync } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const TOKEN = '8896772547:AAGQlbVFW1zxD4AoB77xMCEtBJkDpk-CA-s';
const CHAT_ID = '143293811';
const API = `https://api.telegram.org/bot${TOKEN}`;
const PROJECT = __dirname;
const APK_PATH = resolve(PROJECT, 'android/app/build/outputs/apk/debug/app-debug.apk');

let lastUpdateId = 0;

async function api(method, body) {
  const url = `${API}/${method}`;
  const opts = { method: 'POST', headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  return res.json();
}

async function sendMessage(text, keyboard) {
  const body = { chat_id: CHAT_ID, text, parse_mode: 'HTML' };
  if (keyboard) body.reply_markup = { inline_keyboard: keyboard };
  return api('sendMessage', body);
}

async function sendApk(caption) {
  const ps = `$URL='${API}/sendDocument';$CHAT='${CHAT_ID}';`
    + `Add-Type -AssemblyName System.Net.Http;`
    + `$c=new-object System.Net.Http.HttpClient;`
    + `$m=new-object System.Net.Http.MultipartFormDataContent;`
    + `$f=[System.IO.FileStream]::new('${APK_PATH.replace(/'/g, "''")}',[System.IO.FileMode]::Open);`
    + `$fc=new-object System.Net.Http.StreamContent($f);`
    + `$fc.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/vnd.android.package-archive');`
    + `$m.Add($fc,'document','elemental-life.apk');`
    + `$m.Add([System.Net.Http.StringContent]::new($CHAT),'chat_id');`
    + (caption ? `$m.Add([System.Net.Http.StringContent]::new('${caption.replace(/'/g, "''")}'),'caption');` : '')
    + `$r=$c.PostAsync($URL,$m).GetAwaiter().GetResult();`
    + `$r.Content.ReadAsStringAsync().GetAwaiter().GetResult()`;
  try {
    const out = execSync(`powershell -NoProfile -Command "${ps.replace(/"/g, '\\"')}"`, { timeout: 60000, encoding: 'utf-8', maxBuffer: 1024 * 1024 });
    return { ok: true, out };
  } catch (e) {
    return { ok: false, out: e.message };
  }
}

function run(cmd) {
  try {
    const out = execSync(cmd, { cwd: PROJECT, timeout: 300000, encoding: 'utf-8', maxBuffer: 1024 * 1024, shell: 'powershell' });
    return { ok: true, out: out.slice(0, 2000) };
  } catch (e) {
    return { ok: false, out: e.message.slice(0, 2000) };
  }
}

const MAIN_KEYBOARD = [
  [{ text: '🔨 Build APK', callback_data: 'build' }],
  [{ text: '📤 Send APK', callback_data: 'send' }],
  [{ text: '📊 Status', callback_data: 'status' }],
  [{ text: '🧪 Smoke test', callback_data: 'smoke' }],
  [{ text: '🔄 Sync & Build', callback_data: 'sync_build' }],
];

async function handleCommand(cmd, args) {
  const cmdName = cmd.replace(/^\//, '');
  switch (cmdName) {
    case 'start':
    case 'menu':
    case 'help':
      return sendMessage(
        '<b>Elemental Life — Telegram Bot</b>\n\n'
        + '/status — статус проекта\n'
        + '/build — собрать APK\n'
        + '/send — отправить APK\n'
        + '/smoke — smoke-тест\n'
        + '/sync — sync + build\n'
        + '/run &lt;cmd&gt; — выполнить команду',
        MAIN_KEYBOARD
      );

    case 'status': {
      const buildOk = existsSync(APK_PATH);
      const apkSize = buildOk ? `${(readFileSync(APK_PATH).length / 1024 / 1024).toFixed(1)} MB` : 'N/A';
      const git = run('git log --oneline -3');
      return sendMessage(
        '<b>Статус проекта</b>\n'
        + `APK: ${buildOk ? '✅' : '❌'} ${apkSize}\n`
        + `<pre>${git.out}</pre>`,
        MAIN_KEYBOARD
      );
    }

    case 'build': {
      await sendMessage('🔨 Building web...', MAIN_KEYBOARD);
      const build = run('npm run build');
      if (!build.ok) return sendMessage(`❌ Build failed:\n<pre>${build.out}</pre>`, MAIN_KEYBOARD);
      await sendMessage('✅ Web build OK. Building APK...', MAIN_KEYBOARD);
      const apk = run('cd android && ./gradlew assembleDebug --no-daemon 2>&1');
      return sendMessage(apk.ok ? '✅ APK built!' : `❌ APK failed:\n<pre>${apk.out}</pre>`, MAIN_KEYBOARD);
    }

    case 'send': {
      if (!existsSync(APK_PATH)) return sendMessage('❌ APK not found. Run /build first.', MAIN_KEYBOARD);
      await sendMessage('📤 Sending APK...', MAIN_KEYBOARD);
      const r = await sendApk('Elemental Life APK');
      return sendMessage(r.ok ? '✅ APK sent!' : `❌ Failed`, MAIN_KEYBOARD);
    }

    case 'sync_build':
    case 'sync': {
      await sendMessage('🔄 Syncing...', MAIN_KEYBOARD);
      const sync = run('npx cap sync android 2>&1');
      if (!sync.ok) return sendMessage(`❌ Sync failed:\n<pre>${sync.out}</pre>`, MAIN_KEYBOARD);
      await sendMessage('✅ Sync OK. Building APK...', MAIN_KEYBOARD);
      const apk = run('cd android && ./gradlew assembleDebug --no-daemon 2>&1');
      return sendMessage(apk.ok ? '✅ APK built!' : `❌ APK failed:\n<pre>${apk.out}</pre>`, MAIN_KEYBOARD);
    }

    case 'smoke': {
      await sendMessage('🧪 Running smoke test...', MAIN_KEYBOARD);
      const test = run('node tests/engine.smoke.test.mjs');
      return sendMessage(test.ok ? `✅ Smoke test passed:\n<pre>${test.out}</pre>` : `❌ Smoke test failed:\n<pre>${test.out}</pre>`, MAIN_KEYBOARD);
    }

    default:
      if (cmdName.startsWith('run ')) {
        const command = cmd.slice(4);
        await sendMessage(`⚡ Running: <code>${command}</code>`, MAIN_KEYBOARD);
        const r = run(command);
        return sendMessage(r.ok ? `✅ OK:\n<pre>${r.out}</pre>` : `❌ Error:\n<pre>${r.out}</pre>`, MAIN_KEYBOARD);
      }
      return sendMessage(`Unknown command: ${cmd}\nUse /help`, MAIN_KEYBOARD);
  }
}

async function poll() {
  const updates = await api('getUpdates', { offset: lastUpdateId + 1, timeout: 30 });
  if (!updates.ok || !updates.result) return;

  for (const u of updates.result) {
    lastUpdateId = u.update_id;
    if (u.message?.text) {
      console.log('📩', u.message.text);
      await handleCommand(u.message.text);
    }
    if (u.callback_query?.data) {
      const data = u.callback_query.data;
      console.log('🔘', data);
      await handleCommand(data);
      await api('answerCallbackQuery', { callback_query_id: u.callback_query.id });
    }
  }
}

async function main() {
  console.log('🤖 Telegram Bot started. Polling...');
  await sendMessage('🤖 <b>Bot connected</b>', MAIN_KEYBOARD);
  while (true) {
    try {
      await poll();
    } catch (e) {
      console.error('Poll error:', e.message);
    }
    await new Promise(r => setTimeout(r, 500));
  }
}

main().catch(e => console.error('Fatal:', e));
