#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git_repo_root() -> Path | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            text=True,
        ).strip()
        return Path(out)
    except Exception:
        return None


def repo_root() -> Path:
    env_root = os.environ.get("OPENCLAW_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    git_root = _git_repo_root()
    if git_root:
        return git_root.resolve()
    return Path(__file__).resolve().parents[2]


def env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser().resolve() if raw else default.resolve()


ROOT = repo_root()
RUNTIME_DIR = env_path("OPENCLAW_RUNTIME_DIR", ROOT / "runtime")
TASKS_DB = env_path("OPENCLAW_TASKS_DB", ROOT / "runtime/tasks/tasks.db")
DIRECTIVES_DB = env_path("OPENCLAW_DIRECTIVES_DB", ROOT / "runtime/directives/directives.db")
STAGE6_RUNTIME_AUDIT_DIR = env_path(
    "OPENCLAW_STAGE6_RUNTIME_AUDIT_DIR",
    ROOT / "invest/stages/stage6/outputs/reports/runtime_audit",
)


def openclaw_home() -> Path:
    raw = os.environ.get("OPENCLAW_HOME", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".openclaw"


def sessions_store() -> Path:
    return env_path(
        "OPENCLAW_SESSIONS_STORE",
        openclaw_home() / "agents/main/sessions/sessions.json",
    )


def llama_model_path() -> Path:
    return env_path(
        "OPENCLAW_LOCAL_MODEL_PATH",
        Path.home() / "models/qwen35/Qwen3.5-35B-A3B-Q4_K_M.gguf",
    )
