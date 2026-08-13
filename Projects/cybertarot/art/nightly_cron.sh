#!/bin/bash
# CyberTarot — Nightly Art Factory launcher
# Запускается по cron: поднимает ComfyUI → ждёт → генерирует → закрывает
# 
# Cron: 0 3 * * * /c/projects/cybertarot/art/nightly_cron.sh

set -e

COMFY_INSTALL="C:/Users/tomas/AppData/Local/Comfy-Desktop/ComfyUI-Installs/Cathedral (1)/ComfyUI"
COMFY_PYTHON="$COMFY_INSTALL/.venv/Scripts/python.exe"
COMFY_MAIN="$COMFY_INSTALL/main.py"
SHAREDPATH="C:/Users/tomas/AppData/Roaming/Comfy Desktop/shared_model_paths.yaml"
PORT=8189
ART_DIR="/c/projects/cybertarot/art"

echo "[$(date)] === Nightly Art Factory START ==="

# 1. Запуск ComfyUI
echo "[$(date)] Starting ComfyUI on port $PORT..."
cd "$COMFY_INSTALL"
PYTHONPATH="" VIRTUAL_ENV="" "$COMFY_PYTHON" -s "$COMFY_MAIN" \
  --port $PORT \
  --disable-async-offload \
  --disable-smart-memory \
  --force-fp16 \
  --extra-model-paths-config "$SHAREDPATH" \
  --listen 127.0.0.1 \
  > /tmp/comfyui-nightly.log 2>&1 &
COMFY_PID=$!
echo "[$(date)] ComfyUI PID: $COMFY_PID"

# 2. Wait for server
echo "[$(date)] Waiting for server..."
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:$PORT/system_stats > /dev/null 2>&1; then
    echo "[$(date)] Server ready after ${i}s"
    break
  fi
  sleep 2
done

if ! curl -s http://127.0.0.1:$PORT/system_stats > /dev/null 2>&1; then
  echo "[$(date)] ✗ ComfyUI failed to start"
  kill $COMFY_PID 2>/dev/null
  exit 1
fi

# 3. Run art factory
echo "[$(date)] Running nightly_art.py..."
cd "$ART_DIR"
python nightly_art.py --model sd15 --denoise 0.65 2>&1
ART_EXIT=$?

# 4. Shutdown ComfyUI
echo "[$(date)] Shutting down ComfyUI (PID $COMFY_PID)..."
kill $COMFY_PID 2>/dev/null || true
sleep 2

echo "[$(date)] === Nightly Art Factory DONE (exit $ART_EXIT) ==="
exit $ART_EXIT
