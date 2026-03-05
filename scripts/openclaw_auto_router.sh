#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

LOCAL_MODEL="Qwen3.5-35B-A3B-Q4_K_M.gguf"
LOCAL_ENDPOINT="http://127.0.0.1:8090/v1/chat/completions"
REMOTE_MODEL="openai-codex/gpt-5.3-codex"
CTX_DIR="/tmp/openclaw_local_ctx"
CTX_FILE="${CTX_DIR}/session.json"
RECENT_TURNS=8
MAX_CTX_CHARS=12000

usage() {
  cat <<'USAGE'
Usage:
  scripts/openclaw_auto_router.sh "요청문장"
  scripts/openclaw_auto_router.sh --run "요청문장"
USAGE
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf 'Error: required command not found: %s\n' "$cmd" >&2
    exit 1
  fi
}

init_context_guard() {
  mkdir -p "$CTX_DIR"
  if [[ ! -f "$CTX_FILE" ]]; then
    printf '{"turns":[]}\n' >"$CTX_FILE"
  fi
}

append_context_turn() {
  local role="$1"
  local content="$2"
  local tmp
  tmp="$(mktemp)"
  jq --arg role "$role" --arg content "$content" \
    '.turns += [{"role":$role,"content":$content}]' \
    "$CTX_FILE" >"$tmp"
  mv "$tmp" "$CTX_FILE"
}

build_recent_context() {
  local raw
  raw="$(jq -r --argjson n "$RECENT_TURNS" '
    (.turns // [])
    | if length > $n then .[(length - $n):] else . end
    | map((.role // "unknown") + ": " + (.content // ""))
    | join("\n")
  ' "$CTX_FILE")"

  if [[ ${#raw} -gt $MAX_CTX_CHARS ]]; then
    printf '%s' "${raw: -$MAX_CTX_CHARS}"
  else
    printf '%s' "$raw"
  fi
}

extract_first_text_payload() {
  local payload="$1"
  local extracted=""

  if extracted="$(printf '%s' "$payload" | jq -er '
    def flatten_content(x):
      if (x|type) == "string" then x
      elif (x|type) == "array" then
        x
        | map(
            if type == "string" then .
            elif type == "object" then (.text // .content // "")
            else "" end
          )
        | join("")
      elif (x|type) == "object" then (x.text // x.content // "")
      else "" end;

    (
      .choices[0].message.content //
      .choices[0].delta.content //
      .output_text //
      .message.content //
      .content //
      .text
    ) as $c
    | flatten_content($c)
    | select(length > 0)
  ' 2>/dev/null)"; then
    printf '%s' "$extracted"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    extracted="$(python3 - "$payload" <<'PY'
import json
import sys

src = sys.argv[1]

def text_from_obj(obj):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        out = []
        for item in obj:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    out.append(item["text"])
                elif isinstance(item.get("content"), str):
                    out.append(item["content"])
        return "".join(out)
    if isinstance(obj, dict):
        for key in ("choices", "output", "data"):
            if key in obj and isinstance(obj[key], list):
                for it in obj[key]:
                    s = text_from_obj(it)
                    if s:
                        return s
        for key in ("message", "delta"):
            if key in obj:
                s = text_from_obj(obj[key])
                if s:
                    return s
        for key in ("content", "text", "output_text"):
            val = obj.get(key)
            if isinstance(val, (str, list, dict)):
                s = text_from_obj(val)
                if s:
                    return s
    return ""

candidates = []
try:
    candidates.append(json.loads(src))
except Exception:
    for line in src.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            candidates.append(json.loads(line))
        except Exception:
            continue

for candidate in candidates:
    text = text_from_obj(candidate)
    if text:
        print(text)
        sys.exit(0)

print(src)
PY
)"
    printf '%s' "$extracted"
    return 0
  fi

  printf '%s' "$payload"
}

classify_intent() {
  local msg="$1"
  local msg_lc
  msg_lc="$(printf '%s' "$msg" | tr '[:upper:]' '[:lower:]')"

  if printf '%s' "$msg_lc" | grep -Eqi '(검증|확인|사실|팩트|재현|테스트|크로스체크|품질점검|논리점검|validate|verification|verify|check|audit|reproduce)'; then
    printf 'verify'
  elif printf '%s' "$msg_lc" | grep -Eqi '(추론|분석|이유|원인|비교|판단|reason|analy[sz]e|analysis|infer|why|tradeoff)'; then
    printf 'reason'
  elif printf '%s' "$msg_lc" | grep -Eqi '(코드|스크립트|함수|버그|디버그|디버깅|개발|구현|짜줘|고쳐줘|리팩토|리팩터링|수정|작성|패치|멀티파일|구조개편|고도화|대공사|code|script|function|bug|debug|fix|patch|implement|refactor|program|multi-?file|architecture)'; then
    printf 'code'
  elif printf '%s' "$msg_lc" | grep -Eqi '(수집|크롤|검색|찾아|리서치|조사|조사해봐|자료|긁어와|가져와|스크래핑|fetch|collect|gather|crawl|scrape|search|lookup|find|ingest|pull|extract)'; then
    printf 'collect'
  else
    printf 'general'
  fi
}

classify_code_level() {
  local msg="$1"
  local msg_lc
  msg_lc="$(printf '%s' "$msg" | tr '[:upper:]' '[:lower:]')"

  if printf '%s' "$msg_lc" | grep -Eqi '(아키텍처|설계|대규모|전체구조|멀티파일|구조개편|고도화|대공사|복잡|최적화|동시성|분산|마이그레이션|architecture|system design|multi-?file|complex|large[- ]scale|optimization|concurrency|distributed|migration|end[- ]to[- ]end)'; then
    printf 'complex'
    return 0
  fi

  if [[ ${#msg} -ge 220 ]]; then
    printf 'complex'
  else
    printf 'simple'
  fi
}

classify_reason_level() {
  local msg="$1"
  local msg_lc
  msg_lc="$(printf '%s' "$msg" | tr '[:upper:]' '[:lower:]')"

  if printf '%s' "$msg_lc" | grep -Eqi '(심층|심화|복합|다요인|트레이드오프|시나리오|민감도|장기전략|복잡|고도화|원인분석|아키텍처|complex|deep|multi[- ]factor|tradeoff|scenario|sensitivity|long[- ]term|architecture|root cause)'; then
    printf 'complex'
    return 0
  fi

  if [[ ${#msg} -ge 220 ]]; then
    printf 'complex'
  else
    printf 'simple'
  fi
}

call_local_model() {
  local user_message="$1"
  local context_text="$2"
  local payload
  local response

  payload="$(jq -n \
    --arg model "$LOCAL_MODEL" \
    --arg ctx "$context_text" \
    --arg msg "$user_message" '
    {
      model: $model,
      messages: [
        {
          role: "system",
          content: "You are OpenClaw local router responder. Use recent context if relevant, answer concisely and concretely."
        },
        {
          role: "user",
          content: ("[recent_context]\n" + $ctx + "\n\n[user_request]\n" + $msg)
        }
      ],
      temperature: 0.2
    }
  ')"

  response="$(curl -fsS -X POST "$LOCAL_ENDPOINT" \
    -H 'Content-Type: application/json' \
    -d "$payload")"

  extract_first_text_payload "$response"
}

call_remote_model() {
  local model="$1"
  local user_message="$2"
  local session_id="$3"
  local response

  openclaw models set "$model" >/dev/null
  response="$(openclaw agent --session-id "$session_id" --message "$user_message" --local --json)"
  extract_first_text_payload "$response"
}

run=false
message=""

if [[ $# -eq 1 ]]; then
  message="$1"
elif [[ $# -eq 2 && "$1" == "--run" ]]; then
  run=true
  message="$2"
else
  usage >&2
  exit 2
fi

if [[ -z "$message" ]]; then
  usage >&2
  exit 2
fi

intent="$(classify_intent "$message")"
code_level="n/a"
reason_level="n/a"
route="local"
model="$LOCAL_MODEL"

if [[ "$intent" == "code" ]]; then
  code_level="$(classify_code_level "$message")"
  if [[ "$code_level" == "complex" ]]; then
    route="remote"
    model="$REMOTE_MODEL"
  fi
elif [[ "$intent" == "reason" ]]; then
  reason_level="$(classify_reason_level "$message")"
  if [[ "$reason_level" == "complex" ]]; then
    route="remote"
    model="$REMOTE_MODEL"
  fi
elif [[ "$intent" == "verify" ]]; then
  route="remote"
  model="$REMOTE_MODEL"
fi

printf 'intent=%s code_level=%s reason_level=%s route=%s model=%s\n' "$intent" "$code_level" "$reason_level" "$route" "$model"

if [[ "$run" != true ]]; then
  exit 0
fi

require_cmd jq
require_cmd curl

primary_text=""
if [[ "$route" == "local" ]]; then
  init_context_guard
  context_text="$(build_recent_context)"
  primary_text="$(call_local_model "$message" "$context_text")"
  append_context_turn "user" "$message"
  append_context_turn "assistant" "$primary_text"
else
  require_cmd openclaw
  remote_session_id="autoroute-$(date +%s)-$RANDOM"
  primary_text="$(call_remote_model "$model" "$message" "$remote_session_id")"
fi

printf '%s
' "$primary_text"

if [[ "$intent" == "code" || "$intent" == "reason" ]]; then
  if [[ "$route" == "local" ]]; then
    require_cmd openclaw
    verify_session_id="autoverify-$(date +%s)-$RANDOM"
    verify_prompt=$(cat <<VERIFY
You are a strict verifier.
Check requirement alignment, correctness, feasibility, and risk.
Return concise corrections or approval.

[intent]
$intent

[user_request]
$message

[primary_answer]
$primary_text
VERIFY
)
    verifier_text="$(call_remote_model "$REMOTE_MODEL" "$verify_prompt" "$verify_session_id")"
    printf '
[auto-verify:%s]
%s
' "$REMOTE_MODEL" "$verifier_text"
  else
    init_context_guard
    local_verify_prompt=$(cat <<VERIFY
다음 결과를 엄격히 검증하세요.
요구사항 일치, 정확성, 실행가능성, 위험을 짧게 점검하고 수정점을 제시하세요.

[intent]
$intent

[원요청]
$message

[1차결과]
$primary_text
VERIFY
)
    verify_context="$(build_recent_context)"
    local_verifier_text="$(call_local_model "$local_verify_prompt" "$verify_context")"
    append_context_turn "user" "$local_verify_prompt"
    append_context_turn "assistant" "$local_verifier_text"
    printf '
[auto-verify:%s]
%s
' "$LOCAL_MODEL" "$local_verifier_text"
  fi
fi
