# HOT
#!/usr/bin/env bash
# Vault Sync — Bidirectional git sync across Tailscale nodes
# Runs every 5 min via cron or inotify

set -euo pipefail

VAULT_LOCAL="/home/thomas/Documents/ObsidianVault"
LIVINGCODE_LOCAL="/home/thomas/LivingCode"
LOG_FILE="/home/thomas/LivingCode/logs/vault_sync.log"

# Remote nodes (Tailscale hostnames)
REMOTES=("unsloth-studio" "dell" "lenovo")

log() {
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

sync_vault() {
    cd "$VAULT_LOCAL" || { log "ERROR: Vault not found at $VAULT_LOCAL"; return 1; }
    
    # Commit local changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        git add -A
        git commit -m "Auto-sync $(date -u +%Y%m%d_%H%M%S)" || true
        log "Committed local changes"
    fi
    
    # Push/pull each remote
    for remote in "${REMOTES[@]}"; do
        log "Syncing with $remote..."
        
        # Add remote if not exists
        if ! git remote | grep -q "^$remote$"; then
            git remote add "$remote" "ssh://$remote/home/thomas/Documents/ObsidianVault" 2>/dev/null || true
        fi
        
        # Fetch and merge
        if git fetch "$remote" main 2>/dev/null; then
            # Try rebase first
            if git rebase "$remote/main" 2>/dev/null; then
                log "  Rebased onto $remote/main"
            else
                # Fallback to merge
                git merge "$remote/main" --no-edit 2>/dev/null || {
                    log "  WARNING: Merge conflict with $remote, manual resolution needed"
                    git merge --abort 2>/dev/null || true
                }
            fi
        else
            log "  $remote unreachable or no main branch"
        fi
        
        # Push our changes
        if git push "$remote" main --force-with-lease 2>/dev/null; then
            log "  Pushed to $remote"
        else
            log "  Push to $remote failed (maybe no changes)"
        fi
    done
}

sync_livingcode() {
    cd "$LIVINGCODE_LOCAL" || { log "ERROR: LivingCode not found"; return 1; }
    
    for remote in "${REMOTES[@]}"; do
        # Sync artifacts
        rsync -avz --delete --timeout=30 \
            "$LIVINGCODE_LOCAL/artifacts/" \
            "thomas@$remote:/home/thomas/LivingCode/artifacts/" 2>>"$LOG_FILE" && \
            log "  Synced artifacts to $remote" || \
            log "  Artifacts sync to $remote failed"
        
        # Sync CompleteProjects
        rsync -avz --delete --timeout=30 \
            "$LIVINGCODE_LOCAL/CompleteProjects/" \
            "thomas@$remote:/home/thomas/LivingCode/CompleteProjects/" 2>>"$LOG_FILE" && \
            log "  Synced CompleteProjects to $remote" || \
            log "  CompleteProjects sync to $remote failed"
        
        # Sync QUEUE.json and nodes
        rsync -avz --timeout=30 \
            "$LIVINGCODE_LOCAL/QUEUE.json" \
            "$LIVINGCODE_LOCAL/nodes/" \
            "thomas@$remote:/home/thomas/LivingCode/" 2>>"$LOG_FILE" && \
            log "  Synced QUEUE/nodes to $remote" || \
            log "  QUEUE/nodes sync to $remote failed"
    done
}

main() {
    log "=== Vault Sync Started ==="
    sync_vault
    sync_livingcode
    log "=== Vault Sync Complete ==="
}

main "$@"