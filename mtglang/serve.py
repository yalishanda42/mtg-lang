"""`mtglang serve`: the single-page gallery on localhost, with saving for the glossary editor."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mtglang.edit import EditError, apply_symbol_edits
from mtglang.render import render_site

MAX_BODY = 1 << 20


def make_handler(root: Path, out: Path, lang: str):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data: dict) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/ping":
                return self._json(200, {"ok": True, "lang": lang})
            if path in ("/", "/index.html"):
                with lock:
                    body = (out / "index.html").read_bytes()
                return self._send(200, body, "text/html; charset=utf-8")
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:
            if self.path != "/api/glossary":
                return self._send(404, b"not found", "text/plain")
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= MAX_BODY:
                return self._json(413, {"ok": False, "errors": ["request too large or empty"]})
            try:
                edits = json.loads(self.rfile.read(n))["edits"]
                assert isinstance(edits, list)
            except (ValueError, KeyError, TypeError, AssertionError):
                return self._json(400, {"ok": False, "errors": ["expected JSON {\"edits\": [...]}"]})
            with lock:
                try:
                    result = apply_symbol_edits(root, edits, lang)
                except EditError as e:
                    return self._json(200, {"ok": False, "errors": e.errors})
                render_site(root, out, lang)
            print(f"saved {len(edits)} symbol edit(s): {result['lines']} line(s) in {result['files']} card file(s)", flush=True)
            self._json(200, {"ok": True, **result})

        def log_message(self, fmt, *args) -> None:   # keep the console quiet except for saves
            pass

    return Handler


def serve(root: Path, out: Path, lang: str = "en", host: str = "127.0.0.1", port: int = 8765) -> None:
    root, out = Path(root), Path(out)
    render_site(root, out, lang)
    httpd = ThreadingHTTPServer((host, port), make_handler(root, out, lang))
    print(f"serving http://{host}:{httpd.server_address[1]}/  (Ctrl-C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
