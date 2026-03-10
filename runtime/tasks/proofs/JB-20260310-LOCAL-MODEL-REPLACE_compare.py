#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PORT = 8090
HOST = "127.0.0.1"
BASE_DIR = Path("/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULT_JSON = BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_compare_{STAMP}.json"
REPORT_MD = BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_compare_{STAMP}.md"
RUN_LOG = BASE_DIR / "JB-20260310-LOCAL-MODEL-REPLACE_run.log"

PROMPT = (
    "아래 지표만 보고 투자 메모 초안을 작성하라. "
    "반드시 한국어 JSON만 출력하고 키는 conclusion, positives, risks, verdict를 사용하라. "
    "positives와 risks는 각각 3개 배열이어야 한다. "
    "지표: 매출 +20%, 영업이익 -5%, 잉여현금흐름 -12%, 부채비율 +10%p, 신규계약 2건, 재고회전일수 악화."
)

MODELS = [
    {
        "label": "Qwen3.5-35B-A3B-Q4_K_M",
        "path": "/Users/jobiseu/models/qwen35/Qwen3.5-35B-A3B-Q4_K_M.gguf",
        "request_model": "Qwen3.5-35B-A3B-Q4_K_M.gguf",
    },
    {
        "label": "Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M",
        "path": "/Users/jobiseu/models/qwen35/Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M.gguf",
        "request_model": "Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M.gguf",
    },
]

SERVER_ARGS_COMMON = [
    "--host", HOST,
    "--port", str(PORT),
    "-c", "12288",
    "-ngl", "99",
    "--flash-attn", "on",
    "--cache-type-k", "q8_0",
    "--cache-type-v", "q8_0",
    "--temp", "0.5",
    "--top-p", "0.9",
    "--top-k", "20",
    "--min-p", "0.02",
    "--repeat-penalty", "1.05",
    "--repeat-last-n", "128",
    "--chat-template-kwargs", '{"enable_thinking": false}',
]


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}] {msg}"
    print(line, flush=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def kill_llama() -> None:
    subprocess.run(["pkill", "-f", "llama-server -m /Users/jobiseu/models/qwen35/"], check=False)
    time.sleep(1.5)


def start_server(model: dict, stderr_log: Path) -> subprocess.Popen:
    cmd = ["llama-server", "-m", model["path"], *SERVER_ARGS_COMMON]
    errf = stderr_log.open("wb")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=errf,
        start_new_session=True,
    )
    proc._stderr_file = errf  # type: ignore[attr-defined]
    return proc


def close_proc(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    try:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        errf = getattr(proc, "_stderr_file", None)
        if errf:
            errf.close()
    except Exception:
        pass


def post_chat(model_name: str, prompt: str, max_tokens: int = 256, timeout: int = 120) -> tuple[dict | None, str | None]:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200:
                return None, f"http_{resp.status}"
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            msg = str(e)
        return None, f"http_error:{e.code}:{msg}"
    except Exception as e:
        return None, str(e)


def wait_until_ready(model: dict, timeout_sec: int = 240) -> tuple[float | None, str | None]:
    started = time.perf_counter()
    last_err = None
    while time.perf_counter() - started < timeout_sec:
        data, err = post_chat(model["request_model"], "ping", max_tokens=8, timeout=15)
        if data and data.get("choices"):
            return round(time.perf_counter() - started, 3), None
        last_err = err
        time.sleep(2)
    return None, last_err or "timeout"


def extract_text(resp: dict) -> str:
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return ""


def extract_usage(resp: dict) -> dict:
    usage = resp.get("usage") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def summarize_runs(runs: list[dict]) -> dict:
    latencies = [r["latency_sec"] for r in runs if r.get("latency_sec") is not None]
    if not latencies:
        return {"avg_latency_sec": None, "min_latency_sec": None, "max_latency_sec": None}
    return {
        "avg_latency_sec": round(statistics.mean(latencies), 3),
        "min_latency_sec": round(min(latencies), 3),
        "max_latency_sec": round(max(latencies), 3),
    }


def main() -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    log("JB-20260310-LOCAL-MODEL-REPLACE compare start")
    original_model = MODELS[0]
    results = {
        "created_at": datetime.now().isoformat(),
        "host": HOST,
        "port": PORT,
        "prompt": PROMPT,
        "server_args_common": SERVER_ARGS_COMMON,
        "models": [],
        "restored_model": original_model["label"],
    }

    active_proc = None
    try:
        for model in MODELS:
            stderr_log = BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_{model['label']}_{STAMP}.stderr.log"
            log(f"switching_to={model['label']}")
            kill_llama()
            active_proc = start_server(model, stderr_log)
            ready_sec, ready_err = wait_until_ready(model)
            model_result = {
                "label": model["label"],
                "path": model["path"],
                "ready_sec": ready_sec,
                "ready_error": ready_err,
                "stderr_log": str(stderr_log),
                "runs": [],
            }
            if ready_sec is None:
                log(f"ready_failed model={model['label']} err={ready_err}")
                results["models"].append(model_result)
                continue
            log(f"ready_ok model={model['label']} ready_sec={ready_sec}")

            for i in range(1, 4):
                started = time.perf_counter()
                resp, err = post_chat(model["request_model"], PROMPT, max_tokens=220, timeout=180)
                elapsed = round(time.perf_counter() - started, 3)
                text = extract_text(resp) if resp else ""
                usage = extract_usage(resp) if resp else {}
                run = {
                    "run": i,
                    "ok": err is None and bool(text),
                    "latency_sec": elapsed,
                    "error": err,
                    "text": text,
                    "text_len": len(text),
                    "usage": usage,
                }
                model_result["runs"].append(run)
                log(f"model={model['label']} run={i} ok={run['ok']} latency_sec={elapsed} text_len={len(text)}")

            model_result["summary"] = summarize_runs(model_result["runs"])
            results["models"].append(model_result)

        # restore original model
        log(f"restoring_model={original_model['label']}")
        kill_llama()
        active_proc = start_server(original_model, BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_restore_{STAMP}.stderr.log")
        restore_ready_sec, restore_err = wait_until_ready(original_model)
        results["restore_status"] = {
            "ok": restore_ready_sec is not None,
            "ready_sec": restore_ready_sec,
            "error": restore_err,
        }
        log(f"restore_ok={restore_ready_sec is not None} ready_sec={restore_ready_sec} err={restore_err}")

    finally:
        close_proc(active_proc)
        # leave the restored model running via fresh spawn
        if results.get("restore_status", {}).get("ok"):
            restore_proc = start_server(original_model, BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_restore_live_{STAMP}.stderr.log")
            restore_ready_sec, restore_err = wait_until_ready(original_model)
            results["restore_live_status"] = {
                "ok": restore_ready_sec is not None,
                "ready_sec": restore_ready_sec,
                "error": restore_err,
            }
            log(f"restore_live_ok={restore_ready_sec is not None} ready_sec={restore_ready_sec} err={restore_err}")
            # intentionally keep running
            if restore_proc.poll() is not None:
                close_proc(restore_proc)

    RESULT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append(f"# JB-20260310-LOCAL-MODEL-REPLACE 비교 리포트 ({STAMP})")
    lines.append("")
    lines.append("## 테스트 조건")
    lines.append(f"- Prompt: `{PROMPT}`")
    lines.append(f"- Server args: `{ ' '.join(['llama-server','-m','<MODEL>', *SERVER_ARGS_COMMON]) }`")
    lines.append("- 각 모델당 동일 프롬프트 3회, temperature=0.0, max_tokens=220")
    lines.append("")
    for m in results["models"]:
        s = m.get("summary") or {}
        lines.append(f"## {m['label']}")
        lines.append(f"- ready_sec: {m.get('ready_sec')}")
        lines.append(f"- avg/min/max latency_sec: {s.get('avg_latency_sec')} / {s.get('min_latency_sec')} / {s.get('max_latency_sec')}")
        lines.append(f"- stderr_log: `{m.get('stderr_log')}`")
        lines.append("")
        for r in m["runs"]:
            lines.append(f"### run {r['run']}")
            lines.append(f"- ok: {r['ok']}")
            lines.append(f"- latency_sec: {r['latency_sec']}")
            lines.append(f"- usage: {json.dumps(r.get('usage') or {}, ensure_ascii=False)}")
            lines.append("- text:")
            lines.append("```json")
            lines.append(r.get("text") or "")
            lines.append("```")
            lines.append("")
    lines.append("## Restore")
    lines.append(json.dumps(results.get("restore_live_status") or results.get("restore_status") or {}, ensure_ascii=False, indent=2))
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    log(f"compare_done json={RESULT_JSON} report={REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
