"""A tiny local HTTP server that lets the window's video player read files the user opened.

The page is served from a local HTTP origin, so it cannot read file paths directly; the player is
given a URL on 127.0.0.1 instead. Only files that were explicitly opened are reachable, each under
a random token, and range requests are honoured so a 50 GB recording streams and seeks without
being copied or read whole. Everything stays on this machine: the server binds to the loopback
address only.
"""
import mimetypes
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CHUNK = 1 << 20


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "UltraShot/1"

    def log_message(self, fmt, *args):   # keep the console quiet
        pass

    def handle(self):
        # the player drops connections freely while seeking; that is not an error worth a traceback
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            pass

    def _file(self):
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) != 2 or parts[0] != "v":
            return None
        return self.server.files.get(parts[1])

    def do_HEAD(self):
        self._serve(head=True)

    def do_GET(self):
        self._serve(head=False)

    def _serve(self, head):
        path = self._file()
        if not path or not os.path.isfile(path):
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or ("video/x-matroska" if path.lower().endswith(".mkv") else "application/octet-stream")
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                if a:
                    start = int(a); end = int(b) if b else size - 1
                else:
                    start = max(0, size - int(b)); end = size - 1
            except ValueError:
                start, end = 0, size - 1
            if start >= size:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.send_header("Content-Length", "0"); self.end_headers(); return
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        length = end - start + 1
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if head:
            return
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    data = fh.read(min(CHUNK, left))
                    if not data:
                        break
                    self.wfile.write(data); left -= len(data)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass


class MediaServer:
    """Serve opened files at http://127.0.0.1:<port>/v/<token>."""

    def __init__(self):
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._srv.daemon_threads = True
        self._srv.handle_error = lambda request, addr: None
        self._srv.files = {}
        self.port = self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True, name="media").start()

    def register(self, path):
        for token, p in self._srv.files.items():
            if p == path:
                return self.url(token)
        token = secrets.token_urlsafe(12)
        self._srv.files[token] = path
        return self.url(token)

    def unregister(self, path):
        for token, p in list(self._srv.files.items()):
            if p == path:
                del self._srv.files[token]

    def url(self, token):
        return f"http://127.0.0.1:{self.port}/v/{token}"

    def close(self):
        try:
            self._srv.shutdown()
        except Exception:
            pass
