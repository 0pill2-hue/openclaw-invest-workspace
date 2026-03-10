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
RESULT_JSON = BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_thinking_speed_compare_{STAMP}.json"
REPORT_MD = BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_thinking_speed_compare_{STAMP}.md"
RUN_LOG = BASE_DIR / "JB-20260310-LOCAL-MODEL-REPLACE_run.log"

PROMPT = (
    "Analyze the company snapshot. "
    "First write exactly 12 numbered findings, each between 18 and 24 English words. "
    "Then output one final compact JSON object with keys thesis, positives, risks, action. "
    "positives and risks must each contain exactly 3 short strings. "
    "Do not use markdown fences. "
    "Data: revenue +20%, operating profit -5%, free cash flow -12%, debt ratio +10pp, "
    "two new contracts, worse inventory days, capex +8%, mild FX tailwind, flat demand guidance, small insider selling."
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

THINKING_MODES = [
    {"label": "current_off", "enable_thinking": False},
    {"label": "thinking_high", "enable_thinking": True},
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
]


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}] {msg}"
    print(line, flush=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def kill_llama() -> None:
    subprocess.run(["pkill", "-f", "llama-server -m /Users/jobiseu/models/qwen35/"], check=False)
    time.sleep(1.5)


def start_server(model: dict, thinking: bool, stderr_log: Path) -> subprocess.Popen:
    cmd = [
        "llama-server",
        "-m",
        model["path"],
        *SERVER_ARGS_COMMON,
        "--chat-template-kwargs",
        json.dumps({"enable_thinking": thinking}),
    ]
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


def post_chat(model_name: str, prompt: str, max_tokens: int = 900, timeout: int = 300) -> tuple[dict | None, str | None]:
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


def wait_until_ready(model: dict, timeout_sec: int = 300) -> tuple[float | None, str | None]:
    started = time.perf_counter()
    last_err = None
    while time.perf_counter() - started < timeout_sec:
        data, err = post_chat(model["request_model"], "ping", max_tokens=8, timeout=20)
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
    completion_tokens = [r.get("usage", {}).get("completion_tokens") for r in runs if r.get("usage", {}).get("completion_tokens") is not None]
    tok_per_sec = [r["completion_tok_per_sec"] for r in runs if r.get("completion_tok_per_sec") is not None]
    text_lens = [r.get("text_len") for r in runs if r.get("text_len") is not None]
    return {
        "avg_latency_sec": round(statistics.mean(latencies), 3) if latencies else None,
        "avg_completion_tokens": round(statistics.mean(completion_tokens), 3) if completion_tokens else None,
        "avg_completion_tok_per_sec": round(statistics.mean(tok_per_sec), 3) if tok_per_sec else None,
        "min_completion_tok_per_sec": round(min(tok_per_sec), 3) if tok_per_sec else None,
        "max_completion_tok_per_sec": round(max(tok_per_sec), 3) if tok_per_sec else None,
        "avg_text_len": round(statistics.mean(text_lens), 1) if text_lens else None,
    }


def main() -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    log("JB-20260310-LOCAL-MODEL-REPLACE thinking speed compare start")
    original_model = MODELS[0]
    original_thinking = False
    results = {
        "created_at": datetime.now().isoformat(),
        "host": HOST,
        "port": PORT,
        "prompt": PROMPT,
        "server_args_common": SERVER_ARGS_COMMON,
        "conditions": [],
        "restored_model": original_model["label"],
        "restored_thinking": original_thinking,
    }

    active_proc = None
    try:
        for model in MODELS:
            for mode in THINKING_MODES:
                thinking = mode["enable_thinking"]
                label = f"{model['label']}::{mode['label']}"
                stderr_log = BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_{model['label']}_{mode['label']}_{STAMP}.stderr.log"
                log(f"switching_to={label}")
                kill_llama()
                active_proc = start_server(model, thinking, stderr_log)
                ready_sec, ready_err = wait_until_ready(model)
                condition_result = {
                    "label": label,
                    "model_label": model["label"],
                    "model_path": model["path"],
                    "thinking_label": mode["label"],
                    "enable_thinking": thinking,
                    "ready_sec": ready_sec,
                    "ready_error": ready_err,
                    "stderr_log": str(stderr_log),
                    "runs": [],
                }
                if ready_sec is None:
                    log(f"ready_failed condition={label} err={ready_err}")
                    results["conditions"].append(condition_result)
                    continue
                log(f"ready_ok condition={label} ready_sec={ready_sec}")

                for i in range(1, 4):
                    started = time.perf_counter()
                    resp, err = post_chat(model["request_model"], PROMPT, max_tokens=900, timeout=300)
                    elapsed = round(time.perf_counter() - started, 3)
                    text = extract_text(resp) if resp else ""
                    usage = extract_usage(resp) if resp else {}
                    completion_tokens = usage.get("completion_tokens")
                    tok_per_sec = round(completion_tokens / elapsed, 3) if completion_tokens and elapsed > 0 else None
                    run = {
                        "run": i,
                        "ok": err is None and bool(text),
                        "latency_sec": elapsed,
                        "error": err,
                        "text": text,
                        "text_len": len(text),
                        "usage": usage,
                        "completion_tok_per_sec": tok_per_sec,
                    }
                    condition_result["runs"].append(run)
                    log(
                        f"condition={label} run={i} ok={run['ok']} latency_sec={elapsed} "
                        f"completion_tokens={completion_tokens} tok_per_sec={tok_per_sec} text_len={len(text)}"
                    )

                condition_result["summary"] = summarize_runs(condition_result["runs"])
                results["conditions"].append(condition_result)

        log(f"restoring_model={original_model['label']}::current_off")
        kill_llama()
        active_proc = start_server(
            original_model,
            original_thinking,
            BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_restore_current_off_{STAMP}.stderr.log",
        )
        restore_ready_sec, restore_err = wait_until_ready(original_model)
        results["restore_status"] = {
            "ok": restore_ready_sec is not None,
            "ready_sec": restore_ready_sec,
            "error": restore_err,
        }
        log(f"restore_ok={restore_ready_sec is not None} ready_sec={restore_ready_sec} err={restore_err}")

    finally:
        close_proc(active_proc)
        if results.get("restore_status", {}).get("ok"):
            restore_proc = start_server(
                original_model,
                original_thinking,
                BASE_DIR / f"JB-20260310-LOCAL-MODEL-REPLACE_restore_live_current_off_{STAMP}.stderr.log",
            )
            restore_ready_sec, restore_err = wait_until_ready(original_model)
            results["restore_live_status"] = {
                "ok": restore_ready_sec is not None,
                "ready_sec": restore_ready_sec,
                "error": restore_err,
            }
            log(f"restore_live_ok={restore_ready_sec is not None} ready_sec={restore_ready_sec} err={restore_err}")
            if restore_proc.poll() is not None:
                close_proc(restore_proc)

    RESULT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append(f"# JB-20260310-LOCAL-MODEL-REPLACE thinking speed compare ({STAMP})")
    lines.append("")
    lines.append("## Test conditions")
    lines.append(f"- Prompt: `{PROMPT}`")
    lines.append(f"- Server args: `{' '.join(['llama-server', '-m', '<MODEL>', *SERVER_ARGS_COMMON, '--chat-template-kwargs', '<thinking_json>'])}`")
    lines.append("- Each condition run 3 times, temperature=0.0, max_tokens=900")
    lines.append("- Approx token speed = completion_tokens / total_latency_sec")
    lines.append("")

    for c in results["conditions"]:
        s = c.get("summary") or {}
        lines.append(f"## {c['label']}")
        lines.append(f"- ready_sec: {c.get('ready_sec')}")
        lines.append(f"- avg_latency_sec: {s.get('avg_latency_sec')}")
        lines.append(f"- avg_completion_tokens: {s.get('avg_completion_tokens')}")
        lines.append(f"- avg_completion_tok_per_sec: {s.get('avg_completion_tok_per_sec')}")
        lines.append(f"- min/max_completion_tok_per_sec: {s.get('min_completion_tok_per_sec')} / {s.get('max_completion_tok_per_sec')}")
        lines.append(f"- avg_text_len: {s.get('avg_text_len')}")
        lines.append(f"- stderr_log: `{c.get('stderr_log')}`")
        lines.append("")
        for r in c["runs"]:
            lines.append(f"### run {r['run']}")
            lines.append(f"- ok: {r['ok']}")
            lines.append(f"- latency_sec: {r['latency_sec']}")
            lines.append(f"- usage: {json.dumps(r.get('usage') or {}, ensure_ascii=False)}")
            lines.append(f"- completion_tok_per_sec: {r.get('completion_tok_per_sec')}")
            lines.append("- text_preview:")
            lines.append("```")
            lines.append((r.get("text") or "")[:1200])
            lines.append("```")
            lines.append("")

    lines.append("## Restore")
    lines.append(json.dumps(results.get("restore_live_status") or results.get("restore_status") or {}, ensure_ascii=False, indent=2))
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    log(f"thinking_speed_compare_done json={RESULT_JSON} report={REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
