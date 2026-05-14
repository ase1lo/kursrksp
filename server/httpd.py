from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .app import MessengerApp
from .config import Settings

CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"


class MessengerRequestHandler(BaseHTTPRequestHandler):
    app = MessengerApp()

    def do_OPTIONS(self):
        self._api()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._api()
        else:
            self._static()

    def do_POST(self):
        self._api()

    def do_PATCH(self):
        self._api()

    def do_DELETE(self):
        self._api()

    def _api(self):
        length = int(self.headers.get("Content-Length", "0"))
        response = self.app.handle(self.command, self.path, dict(self.headers), self.rfile.read(length))
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.body())

    def _static(self):
        requested = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        target = (CLIENT_DIR / requested).resolve()
        if CLIENT_DIR not in target.parents and target != CLIENT_DIR:
            self.send_error(404)
            return
        if not target.exists() or target.is_dir():
            target = CLIENT_DIR / "index.html"
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "text/plain; charset=utf-8"
        if target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        if target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
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
