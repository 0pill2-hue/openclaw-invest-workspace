#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "$0")/.." && pwd)/common_env.sh"

MODEL_PATTERN="llama-server.*$(basename "$OPENCLAW_LOCAL_MODEL_PATH")"

pkill -f "$MODEL_PATTERN" || true
nohup llama-server \
  -m "$OPENCLAW_LOCAL_MODEL_PATH" \
  --host "$OPENCLAW_LOCAL_HOST" \
  --port "$OPENCLAW_LOCAL_PORT" \
  -c "$OPENCLAW_LOCAL_CTX" \
  -ngl 99 \
  --flash-attn on \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --temp 0.5 \
  --top-p 0.9 \
  --top-k 20 \
  --min-p 0.02 \
  --repeat-penalty 1.05 \
  --repeat-last-n 128 \
  --chat-template-kwargs '{"enable_thinking": false}' \
  >/tmp/llama-server.log 2>&1 &

sleep 2
openclaw gateway restart
openclaw status --deep
