from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .app import MessengerApp
from .config import Settings

CLIENT_DIR = (Path(__file__).resolve().parent.parent / "client").resolve()


def static_content_type(path):
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "application/javascript; charset=utf-8"
    return "text/plain; charset=utf-8"


def resolve_static_target(raw_path):
    requested = raw_path.split("?", 1)[0].lstrip("/") or "index.html"
    target = (CLIENT_DIR / requested).resolve()
    if CLIENT_DIR not in target.parents and target != CLIENT_DIR:
        return None
    if not target.exists() or target.is_dir():
        target = CLIENT_DIR / "index.html"
    return target if target.exists() and target.is_file() else None


class MessengerRequestHandler(BaseHTTPRequestHandler):
    app = None

    def do_OPTIONS(self):
        self._safe(self._api)

    def do_GET(self):
        self._safe(self._api if self.path.startswith("/api/") else self._static)

    def do_POST(self):
        self._safe(self._api)

    def do_PATCH(self):
        self._safe(self._api)

    def do_DELETE(self):
        self._safe(self._api)

    def _safe(self, handler):
        try:
            handler()
        except Exception as exc:
            print("HTTP handler error: {}".format(exc), flush=True)
            self.send_error(500, "Internal server error")

    def _api(self):
        if self.app is None:
            self.app = MessengerApp(Settings.from_env())
        length = int(self.headers.get("Content-Length", "0"))
        response = self.app.handle(self.command, self.path, dict(self.headers), self.rfile.read(length))
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.body())

    def _static(self):
        target = resolve_static_target(self.path)
        if target is None:
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", static_content_type(target))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)


def main():
    settings = Settings.from_env()
    MessengerRequestHandler.app = MessengerApp(settings)
    if settings.app_env != "test":
        MessengerRequestHandler.app.seed_demo()
    server = ThreadingHTTPServer(("0.0.0.0", settings.port), MessengerRequestHandler)
    print("Listening on http://0.0.0.0:{}".format(settings.port), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
