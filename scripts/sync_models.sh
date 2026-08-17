#!/usr/bin/env bash
# Model Sync — Sync Ollama models across Tailscale nodes
# Run weekly or when new model needed

set -euo pipefail

LOG_FILE="/home/thomas/LivingCode/logs/model_sync.log"
MODEL_REGISTRY="/home/thomas/LivingCode/model_registry.local.json"

log() {
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Source nodes with models (in priority order)
MODEL_SOURCES=("unsloth-studio" "dell" "lenovo")

sync_models() {
    if [[ ! -f "$MODEL_REGISTRY" ]]; then
        log "ERROR: Model registry not found at $MODEL_REGISTRY"
        return 1
    fi
    
    # Parse models from registry
    models=$(jq -r '.models[] | select(.loaded == false) | .name' "$MODEL_REGISTRY" 2>/dev/null || echo "")
    
    if [[ -z "$models" ]]; then
        log "All models already loaded locally"
        return 0
    fi
    
    for model in $models; do
        log "Ensuring model $model is available..."
        
        # Check if already in ollama
        if ollama list | grep -q "^$model "; then
            log "  $model already in Ollama"
            # Update registry
            jq --arg m "$model" '.models |= map(if .name == $m then .loaded = true else . end)' "$MODEL_REGISTRY" > "$MODEL_REGISTRY.tmp" && mv "$MODEL_REGISTRY.tmp" "$MODEL_REGISTRY"
            continue
        fi
        
        # Try pulling from each source
        pulled=false
        for source in "${MODEL_SOURCES[@]}"; do
            log "  Trying to pull $model from $source..."
            if ssh "$source" "ollama list | grep -q '^$model '" 2>/dev/null; then
                # Source has it, pull via ollama (will use local cache if available)
                if ollama pull "$model" 2>>"$LOG_FILE"; then
                    log "  Pulled $model via Ollama"
                    pulled=true
                    break
                fi
            fi
            
            # Try rsync from source's ollama models dir
            if rsync -avz --progress --timeout=300 \
                "thomas@$source:~/.ollama/models/manifests/registry.ollama.ai/library/${model//:/@}/" \
                "~/.ollama/models/manifests/registry.ollama.ai/library/${model//:/@}/" 2>>"$LOG_FILE"; then
                if rsync -avz --progress --timeout=300 \
                    "thomas@$source:~/.ollama/models/blobs/" \
                    "~/.ollama/models/blobs/" 2>>"$LOG_FILE"; then
                    log "  Synced $model from $source via rsync"
                    pulled=true
                    break
                fi
            fi
        done
        
        if [[ "$pulled" == "true" ]]; then
            jq --arg m "$model" '.models |= map(if .name == $m then .loaded = true else . end)' "$MODEL_REGISTRY" > "$MODEL_REGISTRY.tmp" && mv "$MODEL_REGISTRY.tmp" "$MODEL_REGISTRY"
        else
            log "  WARNING: Could not pull $model from any source"
        fi
    done
}

main() {
    log "=== Model Sync Started ==="
    sync_models
    log "=== Model Sync Complete ==="
}

main "$@"