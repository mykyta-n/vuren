"""Debatviewer: speel een opgeslagen debat af in je browser.

Start met `uv run viewer` (leest demo/pitch) of `uv run viewer <map-of-trace.json>`.
Poort via VIEWER_PORT (standaard 8100).
"""
import http.server
import os
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
MEDIA_TYPES = {".png": "image/png", ".ttf": "font/ttf"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doel = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "demo" / "pitch"
    map_ = doel.parent if doel.is_file() else doel
    port = int(os.getenv("VIEWER_PORT", "8100"))

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pad = self.path.split("?")[0]
            if pad in ("/", "/index.html"):
                return self.stuur(ROOT / "viewer.html", "text/html; charset=utf-8")
            if pad == "/pitch":
                return self.stuur(ROOT / "pitch.html", "text/html; charset=utf-8")
            if pad == "/viewer.js":
                return self.stuur(ROOT / "viewer.js", "text/javascript; charset=utf-8")
            if pad == "/viewer.css":
                return self.stuur(ROOT / "viewer.css", "text/css; charset=utf-8")
            bestand = Path(pad)
            if bestand.parent in (Path("/"), Path("/assets")) and bestand.suffix in MEDIA_TYPES:
                asset = ASSETS / bestand.name
                if asset.is_file() and not asset.is_symlink():
                    return self.stuur(asset, MEDIA_TYPES[bestand.suffix])
            if pad in ("/trace.json", "/verdict.json"):
                return self.stuur(map_ / pad[1:], "application/json; charset=utf-8")
            self.send_error(404)

        def stuur(self, bestand, soort):
            if not bestand.exists():
                return self.send_error(404)
            data = bestand.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", soort)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Debatviewer op {url} (leest {map_}). Stop met Ctrl+C.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
