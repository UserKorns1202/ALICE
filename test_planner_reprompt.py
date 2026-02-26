import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time

REQUEST_COUNT = {"n": 0}

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj):
        data = json.dumps(obj).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get('content-length', 0))
        _ = self.rfile.read(length) if length else b''
        REQUEST_COUNT['n'] += 1
        if REQUEST_COUNT['n'] == 1:
            # First reply: short ack
            self._send_json({'response': 'Okay.'})
        else:
            # Second reply: a numbered list
            self._send_json({'response': '1. RUN: echo hello\n2. RUN: echo world'})

    def log_message(self, format, *args):
        return

def run_server():
    srv = HTTPServer(('127.0.0.1', 5001), Handler)
    srv.serve_forever()

if __name__ == '__main__':
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(0.5)
    from agents import Planner
    p = Planner()
    steps = p.plan_with_llm('Run a quick demo', kevin_chat_url='http://127.0.0.1:5001')
    print('Returned steps:', steps)
    # Give server a moment to finish any pending logs
    time.sleep(0.2)
