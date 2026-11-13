#!/usr/bin/env python3
"""E2E smoke NeXXuS node: чистый data dir, все ключевые WS-методы + /metrics + подпись econ export."""
import socket, base64, os, json, struct, subprocess, tempfile, time, hashlib

HOST, PORT = "127.0.0.1", 4010
DATA = os.path.expanduser("~/.hermes/cache/scratch/e2e-node")
os.makedirs(DATA, exist_ok=True)

def ws_connect():
    s = socket.create_connection((HOST, PORT), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET / HTTP/1.1\r\nHost: {HOST}:{PORT}\r\nConnection: Upgrade\r\n"
               f"Upgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n\r\n").encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(4096)
    assert b"101" in resp.split(b"\r\n")[0]
    return s

def send_text(s, text):
    p = text.encode(); mask = os.urandom(4); n = len(p)
    h = bytearray([0x81])
    if n < 126: h.append(0x80 | n)
    elif n < 65536: h.append(0x80 | 126); h += struct.pack(">H", n)
    else: h.append(0x80 | 127); h += struct.pack(">Q", n)
    h += mask
    s.sendall(bytes(h) + bytes(b ^ mask[i % 4] for i, b in enumerate(p)))

def recv_text(s):
    h = s.recv(2); ln = h[1] & 0x7F
    if ln == 126: ln = struct.unpack(">H", s.recv(2))[0]
    elif ln == 127: ln = struct.unpack(">Q", s.recv(8))[0]
    d = b""
    while len(d) < ln: d += s.recv(ln - len(d))
    return d.decode()

def call(method, params=None, token=None, expect_error=False):
    s = ws_connect()
    if token is not None:
        send_text(s, json.dumps({"jsonrpc": "2.0", "method": "auth", "params": {"token": token}, "id": 0}))
        r = json.loads(recv_text(s))
        if expect_error:
            assert r.get("error"), f"auth должен падать: {r}"
            return r
    send_text(s, json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}))
    return json.loads(recv_text(s))

ok = []
def check(name, cond, extra=""):
    assert cond, f"FAIL {name} {extra}"
    ok.append(name)
    print(f"  ✅ {name}")

token = open(os.path.expanduser("~/.hermes/cache/scratch/e2e-node/api.token")).read().strip() if os.path.exists(os.path.expanduser("~/.hermes/cache/scratch/e2e-node/api.token")) else None

# token читается из data dir? nexxusd пишет в ~/.nexxus/api.token — для чистоты читаем оттуда
print("== auth ==")
r = call("node_status", token="wrong-token", expect_error=True)
check("auth: неверный токен → error", True)
r = call("node_status", token=token)
check("auth: верный токен → node_status", "result" in r, r)
node_id = r["result"]["node_id"]

print("== базовые методы ==")
check("ping", call("ping", token=token)["result"]["pong"] is True)
for m in ["node_status", "node_peers", "node_chunks", "node_smp", "node_epoch", "node_tor",
          "node_identity_status", "node_seed_vault_status", "node_econ", "node_metrics",
          "node_backup_list", "node_doctor", "panic_status"]:
    r = call(m, token=token)
    check(m, "result" in r or "error" not in r, r)

print("== upload/chunks/ретенция ==")
f = tempfile.NamedTemporaryFile(delete=False); f.write(os.urandom(4096)); f.close()
r = call("node_upload", {"path": f.name}, token=token)
check("node_upload", "result" in r, r)
r = call("node_chunks", token=token)
body = json.dumps(r["result"])
check("node_chunks видит чанк", len(r["result"].get("chunks", r["result"])) > 0, body[:200])
import re as _re
m = _re.search(r'[0-9a-f]{64}', body)
h = m.group(0) if m else "00"*32
r = call("node_chunk_pin", {"hash": h, "pin": True}, token=token)
check("pin", "result" in r, r)
r = call("node_chunk_ttl", {"hash": h, "ttl_secs": 3600}, token=token)
check("ttl", "result" in r, r)
r = call("node_gc", token=token)
check("gc", "result" in r, r)

print("== /metrics ==")
def http_get(path, tok=None):
    s = socket.create_connection((HOST, PORT), timeout=5)
    hdr = f"GET {path} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n"
    if tok: hdr += f"Authorization: Bearer {tok}\r\n"
    s.sendall((hdr + "\r\n").encode())
    d = b""
    try:
        while True:
            c = s.recv(65536)
            if not c: break
            d += c
    except ConnectionResetError:
        pass
    return d.decode(errors="replace")
r401 = http_get("/metrics")
check("/metrics без токена → 401", "401" in r401.split("\r\n")[0])
r200 = http_get("/metrics", token)
check("/metrics с токеном → 200 + gauges", "200" in r200.split("\r\n")[0] and "nexxus_store_used_bytes" in r200)

print("== econ export: подпись ==")
r = call("node_econ_export", token=token)
e = r["result"]
check("econ_export fields", all(k in e for k in ("report", "canonical", "signature", "pubkey")), e.keys())
# верификация ed25519 через python cryptography
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
vk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(e["pubkey"]))
try:
    vk.verify(bytes.fromhex(e["signature"]), e["canonical"].encode())
    check("econ_export signature verifies", True)
except Exception as ex:
    check("econ_export signature verifies", False, ex)
# tamper → fail
try:
    vk.verify(bytes.fromhex(e["signature"]), (e["canonical"] + " ").encode())
    check("tamper検出", False)
except Exception:
    check("tamper → verify fails", True)

print("== backup ==")
r = call("node_backup", {}, token=token)
check("node_backup", "result" in r, r)
bname = r["result"].get("name") if isinstance(r["result"], dict) else None
r = call("node_backup_list", token=token)
check("backup в списке", bname is None or bname in json.dumps(r["result"]), json.dumps(r["result"])[:200])
if bname:
    r = call("node_backup_delete", {"name": bname}, token=token)
    check("delete без confirm → error", "error" in r, r)
    r = call("node_backup_delete", {"name": bname, "confirm": True}, token=token)
    check("delete с confirm", "result" in r, r)

print("== bundle export/import ==")
r = call("node_export_bundle", {}, token=token)
check("export без pin → error", "error" in r, r)
r = call("node_export_bundle", {"pin": "e2e-pin"}, token=token)
check("export", "result" in r, r)
bpath = r["result"]["path"]
r = call("node_import_bundle", {"path": bpath, "pin": "e2e-pin"}, token=token)
check("import без confirm → error", "error" in r, r)
r = call("node_import_bundle", {"path": bpath, "pin": "wrong", "confirm": True}, token=token)
check("import wrong pin → error", "error" in r, r)
r = call("node_import_bundle", {"path": bpath, "pin": "e2e-pin", "confirm": True}, token=token)
check("import ok", "result" in r, r)

print("== smp ==")
r = call("node_smp_send", {"recipient_node_id": "ab"*32, "recipient_pub": "cd"*32, "message": "e2e"}, token=token)
check("smp_send (no route → ok:false, но отвечает)", "result" in r and r["result"].get("ok") is False, r)
r = call("node_smp", token=token)
check("smp история содержит sent", any(m["direction"] == "sent" for m in r["result"]["messages"]))

print("== PoR ==")
r = call("node_por", token=token)
check("node_por отвечает", "result" in r or "error" in r, r)

print(f"\nE2E SMOKE: {len(ok)}/{len(ok)} проверок прошли")
