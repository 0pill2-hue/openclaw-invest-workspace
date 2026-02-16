import base64
import os
import json
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler

# --- CONFIGURATION ---
USERNAME = "admin"
PASSWORD = "pill"
DIRECTORY = "/Users/jobiseu/.openclaw/workspace/invest/web"
PORT = 18888
# ---------------------

class AuthHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="JoBis Secure Command Center"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def check_auth(self):
        auth_header = self.headers.get('Authorization')
        if auth_header is None:
            self.do_AUTHHEAD()
            self.wfile.write(b'no auth header received')
            return False
        elif auth_header == 'Basic ' + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode():
            return True
        else:
            self.do_AUTHHEAD()
            self.wfile.write(b'not authenticated')
            return False

    def do_GET(self):
        if self.check_auth():
            SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if not self.check_auth():
            return

        if self.path == '/api/command':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            command_text = payload.get('text', '')

            print(f"Received web command: {command_text}")

            reply = ""
            try:
                # FIX: Use a stable session-id for the web console
                proc = subprocess.run(
                    ["openclaw", "agent", "--message", command_text, "--session-id", "web-console-session", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                print(f"Agent raw output: {proc.stdout}")
                
                if proc.returncode == 0:
                    try:
                        # Attempt to find the last valid JSON object in the output
                        lines = proc.stdout.strip().split('\n')
                        res_json = None
                        for line in reversed(lines):
                            try:
                                res_json = json.loads(line)
                                if 'reply' in res_json or 'result' in res_json:
                                    break
                            except: continue
                        
                        if res_json:
                            result = res_json.get('result', {})
                            payloads = result.get('payloads', [])
                            if payloads and isinstance(payloads, list):
                                reply = payloads[0].get('text', '답변 내용이 없습니다.')
                            elif 'reply' in res_json:
                                reply = res_json.get('reply')
                            else:
                                reply = "명령을 수행했으나 답변 텍스트를 추출하지 못했습니다."
                        else:
                            reply = "명령 결과 JSON 파싱 실패."
                    except Exception as parse_err:
                        reply = f"파싱 오류: {str(parse_err)}"
                else:
                    reply = f"명령 실행 오류: {proc.stderr}"
            except Exception as e:
                reply = f"시스템 내부 오류: {str(e)}"

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"reply": reply})
            self.wfile.write(response.encode('utf-8'))

if __name__ == '__main__':
    print(f"Starting secure command server on port {PORT}...")
    server = HTTPServer(('127.0.0.1', PORT), AuthHandler)
    server.serve_forever()
