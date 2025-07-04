import os
import socketserver
import threading
from datetime import datetime
import re

_LOG_DIR = os.path.join(os.getcwd(), 'logsDomofon')
_PORT = 5514
_server_thread = None
_server = None
_server_started = False
_lock = threading.Lock()
_log_positions = {}

RFC3164_RE = re.compile(r'<(\d+)>([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+([^ ]+)\s+(.*)')


def _ensure_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)


def _log_server_message(msg: str) -> None:
    _ensure_log_dir()
    path = os.path.join(_LOG_DIR, 'server.log')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(path, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} {msg}\n")


class _SyslogHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].decode('utf-8', errors='replace').strip()
        ip, port = self.client_address
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        match = RFC3164_RE.match(data)
        if match:
            pri = int(match.group(1))
            facility = pri >> 3
            severity = pri & 7
            timestamp = match.group(2)
            host = match.group(3)
            msg = match.group(4)
            line = (
                f"{now} [{ip}:{port}] PRI={pri} (fac={facility}, sev={severity}), "
                f"time={timestamp}, host={host}, msg={msg}\n"
            )
            filename = f"{ip}_{datetime.now().strftime('%d.%m.%Y')}.log"
            path = os.path.join(_LOG_DIR, filename)
        else:
            line = f"{now} [{ip}:{port}] RAW: {data}\n"
            path = os.path.join(_LOG_DIR, 'raw.log')
        _ensure_log_dir()
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line)
            f.flush()


def _run_server():
    global _server, _server_started
    server = socketserver.ThreadingUDPServer(('0.0.0.0', _PORT), _SyslogHandler)
    _server = server
    _log_server_message(f'Started on UDP :{_PORT}')
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        _log_server_message('Stopped')
        with _lock:
            _server_started = False
            _server = None


def start_syslog_server() -> None:
    global _server_thread, _server_started
    with _lock:
        if _server_started:
            return
        _server_started = True
        _server_thread = threading.Thread(target=_run_server, daemon=True)
        _server_thread.start()


def stop_syslog_server() -> None:
    global _server_thread
    with _lock:
        if not _server_started or _server is None:
            return
        _server.shutdown()
    if _server_thread:
        _server_thread.join()
        _server_thread = None


def LogDomofon(ip: str, follow: bool = False):
    """Return logs for given IP. If ``follow`` is True, only new lines since the
    last call are returned."""
    _ensure_log_dir()
    filename = f"{ip}_{datetime.now().strftime('%d.%m.%Y')}.log"
    path = os.path.join(_LOG_DIR, filename)
    if follow:
        pos = _log_positions.get(path, 0)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                f.seek(pos)
                lines = f.readlines()
                _log_positions[path] = f.tell()
                return lines
        except FileNotFoundError:
            return []
    else:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.readlines()
        except FileNotFoundError:
            return []
