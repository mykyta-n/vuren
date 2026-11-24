"""Lokale live- en demoviewers voor de Raad van Achrona."""
import argparse
import http.server
import os
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
MEDIA_TYPES = {".png": "image/png", ".ttf": "font/ttf"}


def serve(map_, port, *, demo=False):
    mode = b"demo" if demo else b"live"
    script = ROOT / ("demo-viewer/replay.js" if demo else "viewer-live.js")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pad = self.path.split("?")[0]
            if pad in ("/", "/index.html"):
                pagina = (ROOT / "viewer.html").read_bytes().replace(b"VIEWER_MODE", mode, 1)
                return self.stuur_data(200, pagina, "text/html; charset=utf-8")
            if pad == "/chamber-mode.js":
                return self.stuur(script, "text/javascript; charset=utf-8")
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
            try:
                data = bestand.read_bytes()
            except FileNotFoundError:
                return self.send_error(404)
            return self.stuur_data(200, data, soort)

        def stuur_data(self, status, data, soort):
            self.send_response(status)
            self.send_header("Content-Type", soort)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        naam = "Demoviewer" if demo else "Liveviewer"
        print(f"{naam} op {url} (leest {map_}). Stop met Ctrl+C.")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description="Volg een live debat.")
    parser.add_argument("map", nargs="?", type=Path, default=ROOT,
                        help="Projectmap of pad naar trace.json")
    parser.add_argument("--port", type=int, default=os.getenv("VIEWER_PORT", "8100"))
    args = parser.parse_args()
    doel = args.map.resolve()
    map_ = doel.parent if doel.is_file() else doel
    if not map_.is_dir():
        parser.error(f"Map niet gevonden: {map_}")
    serve(map_, args.port)


def demo_main():
    parser = argparse.ArgumentParser(description="Speel een opgeslagen debat af.")
    parser.add_argument("map", nargs="?", type=Path,
                        help="Map met trace.json en verdict.json (standaard de projectmap)")
    parser.add_argument("--port", type=int, default=os.getenv("DEMO_VIEWER_PORT", "8104"))
    args = parser.parse_args()
    map_ = args.map.resolve() if args.map is not None else ROOT
    ontbreekt = [naam for naam in ("trace.json", "verdict.json") if not (map_ / naam).is_file()]
    if ontbreekt:
        melding = f"Ontbreekt in {map_}: {', '.join(ontbreekt)}."
        if args.map is None:
            melding += " Geef een map met een opgeslagen run op, of gebruik 'uv run demo-viewer demo/pitch' voor de oefendemo."
        parser.error(melding)
    serve(map_, args.port, demo=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--demo"]:
        del sys.argv[1]
        demo_main()
    else:
        main()
