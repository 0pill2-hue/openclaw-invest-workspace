import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

HOST = "127.0.0.1"
PORT = 18889
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPORT_DIR = os.path.join(ROOT, "reports", "regular")
INDEX_PATH = os.path.join(REPORT_DIR, "index.json")


def load_index():
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"reports": []}
    return {"reports": []}


def render_home():
    os.makedirs(REPORT_DIR, exist_ok=True)
    data = load_index()
    reports = data.get("reports", [])[:200]
    items = []
    for r in reports:
        title = r.get("title", "(제목 없음)")
        ts = r.get("timestamp", "")
        kind = r.get("kind", "unknown")
        path = r.get("path", "")
        items.append(
            f'<li><a href="/files/{path}">{title}</a> '
            f'<small>[{kind}] {ts}</small></li>'
        )

    body = "\n".join(items) if items else "<li>아직 보고서가 없습니다.</li>"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""
<!doctype html>
<html lang=\"ko\"><head><meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>정기보고 게시판</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 24px; line-height: 1.5; }}
h1 {{ margin: 0 0 8px; }}
small, .muted {{ color: #666; }}
ul {{ padding-left: 20px; }}
li {{ margin: 6px 0; }}
code {{ background:#f3f3f3; padding:2px 6px; border-radius:6px; }}
</style></head><body>
<h1>정기보고 게시판</h1>
<p class=\"muted\">최근 업데이트: {now}</p>
<p class=\"muted\">저장 위치: <code>reports/regular</code></p>
<ul>{body}</ul>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            html = render_home().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        if self.path.startswith("/files/"):
            rel = unquote(self.path[len("/files/"):]).lstrip("/")
            safe_path = os.path.normpath(os.path.join(REPORT_DIR, rel))
            if not safe_path.startswith(REPORT_DIR):
                self.send_error(403)
                return
            if not os.path.exists(safe_path):
                self.send_error(404)
                return
            with open(safe_path, "rb") as f:
                data = f.read()
            ctype = "text/markdown; charset=utf-8" if safe_path.endswith(".md") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404)


if __name__ == "__main__":
    os.makedirs(REPORT_DIR, exist_ok=True)
    print(f"Regular report board: http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
