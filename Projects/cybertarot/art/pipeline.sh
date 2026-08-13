#!/bin/bash
# ============================================================
# CyberTarot Nightly Art Pipeline — Multi-stage
# TT228 Creative Collective
#
# Stage 1: ComfyUI → txt2img 22 cards (SD1.5, 512×768)
# Stage 2: ComfyUI → ESRGAN upscale (4x, → 2048×3072)
# Stage 3: [future] Ollama Qwen3 → AI interpretations
#
# Каждый этап: загрузка модели → работа → выгрузка VRAM →
# триггер следующего → shutdown
#
# Cron: 0 3 * * * /c/projects/cybertarot/art/pipeline.sh
# ============================================================

set -e

# --- Paths ---
COMFY_INSTALL="C:/Users/tomas/AppData/Local/Comfy-Desktop/ComfyUI-Installs/Cathedral (1)/ComfyUI"
COMFY_PYTHON="$COMFY_INSTALL/.venv/Scripts/python.exe"
COMFY_MAIN="$COMFY_INSTALL/main.py"
SHAREDPATH="C:/Users/tomas/AppData/Roaming/Comfy Desktop/shared_model_paths.yaml"
PORT=8189
ART_DIR_WIN="C:/projects/cybertarot/art"
ART_DIR="/c/projects/cybertarot/art"
CARDS_DIR_WIN="$ART_DIR_WIN/cards"
CARDS_DIR="$ART_DIR/cards"
UPSCALED_DIR_WIN="$ART_DIR_WIN/cards_hd"
UPSCALED_DIR="$ART_DIR/cards_hd"
mkdir -p "$UPSCALED_DIR"

# --- Helpers ---
log() { echo "[$(date '+%H:%M:%S')] $1"; }

free_vram() {
  log "  Freeing VRAM..."
  curl -s -X POST "http://127.0.0.1:$PORT/free" \
    -H "Content-Type: application/json" \
    -d '{"unload_models": true, "free_memory": true}' > /dev/null 2>&1 || true
  sleep 3
}

start_comfy() {
  log "Starting ComfyUI on :$PORT..."
  cd "$COMFY_INSTALL"
  PYTHONPATH="" VIRTUAL_ENV="" "$COMFY_PYTHON" -s "$COMFY_MAIN" \
    --port $PORT \
    --disable-async-offload \
    --disable-smart-memory \
    --force-fp16 \
    --extra-model-paths-config "$SHAREDPATH" \
    --listen 127.0.0.1 \
    > /tmp/comfyui-pipeline.log 2>&1 &
  COMFY_PID=$!
  log "  PID: $COMFY_PID"

  # Wait for readiness
  for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:$PORT/system_stats > /dev/null 2>&1; then
      log "  Ready after ${i}s"
      return 0
    fi
    sleep 2
  done
  log "  ✗ ComfyUI failed to start"
  return 1
}

stop_comfy() {
  free_vram
  log "Stopping ComfyUI (PID $COMFY_PID)..."
  kill $COMFY_PID 2>/dev/null || true
  sleep 3
  # Force kill if still alive
  kill -9 $COMFY_PID 2>/dev/null || true
  sleep 1
}

# ============================================================
# STAGE 1: GENERATION — txt2img SD1.5
# ============================================================
stage1_generate() {
  log "=== STAGE 1: Generation (SD1.5, 512×768) ==="

  start_comfy || { log "✗ Stage 1 aborted"; return 1; }

  log "Running nightly_art.py (txt2img)..."
  cd "$ART_DIR"
  python nightly_art.py --model sd15 --denoise 0.65 2>&1
  local art_exit=$?

  stop_comfy

  if [ $art_exit -ne 0 ]; then
    log "✗ Stage 1 failed (exit $art_exit)"
    return 1
  fi

  local count=$(ls "$CARDS_DIR"/*.png 2>/dev/null | wc -l)
  log "✓ Stage 1 done: $count cards in $CARDS_DIR"
  return 0
}

# ============================================================
# STAGE 2: UPSCALE — ESRGAN 4x
# ============================================================
stage2_upscale() {
  log "=== STAGE 2: Upscale (4x Python → 2048×3072) ==="

  local cards_count=$(ls "$CARDS_DIR"/*.png 2>/dev/null | wc -l)
  if [ "$cards_count" -eq 0 ]; then
    log "✗ No cards to upscale"
    return 1
  fi

  log "Running Python upscaler on $cards_count cards..."
  cd "$ART_DIR"
  python upscale_simple.py --input "$CARDS_DIR_WIN" --output "$UPSCALED_DIR_WIN" 2>&1
  local upscale_exit=$?

  if [ $upscale_exit -ne 0 ]; then
    log "⚠ Stage 2 failed (exit $upscale_exit) — keeping originals"
    return 0  # non-fatal
  fi

  local hd_count=$(ls "$UPSCALED_DIR"/*.png 2>/dev/null | wc -l)
  log "✓ Stage 2 done: $hd_count HD cards in $UPSCALED_DIR"
  return 0
}

# ============================================================
# STAGE 3: POST-PROCESS — color correction, border, watermark
# ============================================================
stage3_postprocess() {
  log "=== STAGE 3: Post-process (border, color, watermark) ==="

  cd "$ART_DIR"
  python postprocess.py --input "$UPSCALED_DIR_WIN" --output "$ART_DIR_WIN/cards_final" 2>&1
  local pp_exit=$?

  if [ $pp_exit -ne 0 ]; then
    log "⚠ Stage 3 failed — using unprocessed cards"
    cp -r "$UPSCALED_DIR"/* "$ART_DIR/cards_final/" 2>/dev/null || true
    return 0
  fi

  local final_count=$(ls "$ART_DIR/cards_final"/*.png 2>/dev/null | wc -l)
  log "✓ Stage 3 done: $final_count final cards"
  return 0
}

# ============================================================
# MAIN PIPELINE
# ============================================================
log "==============================="
log "CyberTarot Nightly Art Pipeline"
log "TT228 Creative Collective"
log "==============================="

STAGE1_OK=0
STAGE2_OK=0
STAGE3_OK=0

stage1_generate && STAGE1_OK=1
if [ $STAGE1_OK -eq 1 ]; then
  stage2_upscale && STAGE2_OK=1
fi
if [ $STAGE2_OK -eq 1 ] || [ $STAGE1_OK -eq 1 ]; then
  stage3_postprocess && STAGE3_OK=1
fi

# Summary
log "==============================="
log "PIPELINE SUMMARY:"
log "  Stage 1 (Generate):    $([ $STAGE1_OK -eq 1 ] && echo '✓ PASS' || echo '✗ FAIL')"
log "  Stage 2 (Upscale):     $([ $STAGE2_OK -eq 1 ] && echo '✓ PASS' || echo '⚠ SKIP')"
log "  Stage 3 (Post-process):$([ $STAGE3_OK -eq 1 ] && echo '✓ PASS' || echo '⚠ SKIP')"
log "==============================="

# Final VRAM cleanup
free_vram 2>/dev/null || true

log "DONE"
exit 0
