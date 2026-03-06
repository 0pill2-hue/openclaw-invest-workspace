#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common_env.sh"

MODEL_PATTERN="llama-server.*$(basename "$OPENCLAW_LOCAL_MODEL_PATH")"

pkill -f "$MODEL_PATTERN" || true
nohup llama-server \
  -m "$OPENCLAW_LOCAL_MODEL_PATH" \
  --port 8090 \
  -c 32768 \
  --temp 0.7 \
  --top-p 0.8 \
  --top-k 20 \
  --min-p 0.0 \
  --chat-template-kwargs '{"enable_thinking": true}' \
  -ngl 99 \
  --flash-attn on \
  >/tmp/llama-server.log 2>&1 &

sleep 2
openclaw gateway restart
openclaw status --deep
