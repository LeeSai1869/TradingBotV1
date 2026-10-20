"""Thin HTTP server for the chart UI.

Serves static files from Section 11's root and dispatches /api/* to routes.py.
"""
from __future__ import annotations
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from . import routes

HERE = Path(__file__).resolve().parent          # Section_11_UI_UX/server/
SECTION_11 = HERE.parent                        # Section_11_UI_UX/
WEB_ROOT = SECTION_11 / "web_root"

routes.SECTION_11 = SECTION_11
routes.UI_CONFIG = SECTION_11 / "config" / "ui_config.json"

PORT = 8000


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from Section 11's root so /chart/, /overlays/, /panels/,
        # /controls/, /web_root/ all resolve as real paths.
        super().__init__(*args, directory=str(SECTION_11), **kwargs)

    def do_GET(self):
        if not self._local_host():
            self._json({"error": "Invalid Host"}, 403)
            return
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/") and parsed.path != "/api/session" and routes.admin_routes.user(self)["role"] == "guest":
            self._json({"error": "Sign in required"}, 401)
            return
        # API dispatch
        status, payload = routes.handle_get(parsed.path, parsed.query, self)
        if status is not None:
            self._json(payload, status)
            return

        # Root → web_root/index.html
        if parsed.path in ("", "/"):
            self.path = "/web_root/index.html"

        return super().do_GET()

    def end_headers(self):
        # Development UI must never execute stale HTML/JS/CSS.
        # This applies to both API responses and static files.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _local_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def do_POST(self):
        if not self._local_host():
            self._json({"error": "Invalid Host"}, 403)
            return
        self.response_cookie = None
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/login", "/api/logout"} and routes.admin_routes.user(self)["role"] == "guest":
            self._json({"error": "Sign in required"}, 401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 16384:
                raise ValueError()
        except ValueError:
            self._json({"error": "Invalid request size"}, 413)
            return
        body = self.rfile.read(length).decode("utf-8") if length else ""
        status, payload = routes.handle_post(parsed.path, body, self)
        if status is not None:
            self._json(payload, status)
            return
        self.send_response(404); self.end_headers()

    def _json(self, obj, status=200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        if getattr(self, "response_cookie", None):
            self.send_header("Set-Cookie", self.response_cookie)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    stop_alerts = routes.alert_routes.alerts.start()
    print(f"chart server on http://localhost:{PORT}/")
    print(f"root:  {SECTION_11}")
    print(f"web:   {WEB_ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        stop_alerts.set()
        server.server_close()


if __name__ == "__main__":
    main()
