import threading
import socket
import json
import time
from typing import Callable, Optional


class BusServer:
    """A minimal TCP-based pub/sub bus for local IPC (newline-delimited JSON).

    Clients may connect and either publish a JSON object of the form
    {"topic": "name", "payload": {...}} (single-line), or remain connected
    to receive any published objects broadcast by the server.
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 8765):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.clients: list[socket.socket] = []
        self.lock = threading.Lock()
        self.running = False

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(8)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                with self.lock:
                    self.clients.append(client)
                threading.Thread(target=self._client_reader, args=(client,), daemon=True).start()
            except Exception:
                time.sleep(0.05)

    def _client_reader(self, client: socket.socket):
        f = None
        try:
            f = client.makefile('rb')
            while True:
                try:
                    line = f.readline()
                except Exception:
                    # Socket problems (client closed/aborted) -> stop quietly
                    break
                if not line:
                    break
                try:
                    text = line.decode('utf-8').strip()
                    obj = json.loads(text)
                except Exception:
                    # Malformed input; ignore and continue reading
                    continue

                # Broadcast received JSON to all clients
                msg = (json.dumps(obj) + '\n').encode('utf-8')
                with self.lock:
                    for c in list(self.clients):
                        try:
                            c.sendall(msg)
                        except Exception:
                            try:
                                c.close()
                            except Exception:
                                pass
                            try:
                                self.clients.remove(c)
                            except ValueError:
                                pass
        finally:
            with self.lock:
                try:
                    if client in self.clients:
                        self.clients.remove(client)
                except Exception:
                    pass
            try:
                if f:
                    f.close()
            except Exception:
                pass
            try:
                client.close()
            except Exception:
                pass

    def stop(self):
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass
        with self.lock:
            for c in list(self.clients):
                try:
                    c.close()
                except Exception:
                    pass
            self.clients = []


def publish(host: str, port: int, topic: str, payload: dict):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    obj = {"topic": topic, "payload": payload}
    s.sendall((json.dumps(obj) + '\n').encode('utf-8'))
    try:
        s.close()
    except Exception:
        pass


def subscribe_forever(host: str, port: int, callback: Callable[[dict], None], stop_event: Optional[threading.Event] = None):
    """Connect to the bus and invoke `callback` for each received message.

    This call blocks until the connection is closed or `stop_event` is set.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    f = s.makefile('rb')
    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            line = f.readline()
            if not line:
                break
            try:
                obj = json.loads(line.decode('utf-8').strip())
            except Exception:
                continue
            try:
                callback(obj)
            except Exception:
                # swallow callback exceptions so subscriber loop continues
                pass
    finally:
        try:
            s.close()
        except Exception:
            pass


def subscribe_once(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    f = s.makefile('rb')
    try:
        line = f.readline()
        if not line:
            return None
        return json.loads(line.decode('utf-8').strip())
    finally:
        try:
            s.close()
        except Exception:
            pass
