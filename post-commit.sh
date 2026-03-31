#!/bin/bash
# Git post-commit hook for ENS Tools improvement
# Install: cp post-commit.sh ~/.git/hooks/post-commit && chmod +x

WORKSPACE="/Users/acc/ens.tools"
LOG_FILE="/Users/acc/.openclaw/workspace/agents/ens-improver/improvement.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Git commit detected, checking for improvements..."

cd "$WORKSPACE"

# Run TypeScript check
if ! npx tsc --noEmit > /tmp/tsc_output.txt 2>&1; then
    ERROR_COUNT=$(grep -c "error TS" /tmp/tsc_output.txt || echo "0")
    log "TypeScript errors found: $ERROR_COUNT"
    
    # Spawn improvement agent
    openclaw sessions_spawn \
        --agent-id main \
        --model "minimax-portal/MiniMax-M2.5" \
        --timeout-seconds 300 \
        --task "Fix TypeScript errors in $WORKSPACE.

Run 'npx tsc --noEmit' to see errors, fix them, then verify with 'npm run build'.
Report what you fixed."
    
    log "Improvement agent spawned for commit $(git rev-parse --short HEAD)"
else
    log "No TypeScript errors - build clean"
fi
