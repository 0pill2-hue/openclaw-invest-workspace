#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
STATIC_DIR = ROOT / "docs/dashboard"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from read_ops import build_overview
from read_stage1 import build_summary as build_stage1_summary
from read_stage2 import build_summary as build_stage2_summary
from read_tasks import get_task_detail

HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
PORT = int(os.environ.get("DASHBOARD_PORT", "8765"))

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "OpenClawDashboard/1.0"

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            body = b"{}"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        rel = "/index.html" if path in {"/", ""} else path
        candidate = (STATIC_DIR / rel.lstrip("/")).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())) or not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(candidate.suffix.lower(), "application/octet-stream"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(candidate.stat().st_size))
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/ops/overview":
            self.send_json(build_overview())
            return
        if path.startswith("/api/tasks/"):
            ticket_id = path.split("/api/tasks/", 1)[1].strip()
            payload = get_task_detail(ticket_id)
            if not payload.get("available"):
                self.send_json({"available": False, "ticket_id": ticket_id, "error": "task not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.send_json(payload)
            return
        if path == "/api/stage1/summary":
            self.send_json(build_stage1_summary())
            return
        if path == "/api/stage2/summary":
            self.send_json(build_stage2_summary())
            return
        self.serve_static(path)

    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        rel = "/index.html" if path in {"/", ""} else path
        candidate = (STATIC_DIR / rel.lstrip("/")).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())) or not candidate.exists() or not candidate.is_file():
            self.send_json({"available": False, "error": "not found", "path": path}, status=HTTPStatus.NOT_FOUND)
            return
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(candidate.suffix.lower(), "application/octet-stream"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    if not STATIC_DIR.exists():
        raise SystemExit(f"missing static dir: {STATIC_DIR}")
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"[dashboard] localhost-only server on http://{HOST}:{PORT}/")
    print("[dashboard] run: python scripts/dashboard/server.py")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
