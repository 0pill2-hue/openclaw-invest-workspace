#!/usr/bin/env bash
set -euo pipefail

MODEL_PATTERN='llama-server.*Qwen3.5-35B-A3B-Q4_K_M.gguf'

pkill -f "$MODEL_PATTERN" || true
nohup llama-server \
  -m /Users/jobiseu/models/qwen35/Qwen3.5-35B-A3B-Q4_K_M.gguf \
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
