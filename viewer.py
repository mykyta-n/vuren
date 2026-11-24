"""Lokale live- en demoviewers voor de Raad van Achrona."""
import argparse
import http.server
import json
import os
import subprocess
import sys
import webbrowser
from threading import Lock
from pathlib import Path

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
MEDIA_TYPES = {".png": "image/png", ".ttf": "font/ttf"}
MODEL_INSTELLINGEN = ("OPENAI_BASE_URL", "OPENAI_API_KEY", "MODEL_KLEIN", "MODEL_GROOT")


class CouncilRun:
    def __init__(self, map_):
        self.map = map_
        self.proces = None
        self.vorige_run = None
        self.slot = Lock()

    def beschikbaar(self):
        return self.map.is_dir() and (
            (self.map / ".env").is_file() or all(os.getenv(key) for key in MODEL_INSTELLINGEN)
        )

    def toestand(self):
        fase = "wacht"
        if self.proces is not None:
            resultaat = self.proces.poll()
            if resultaat is None:
                fase = "bezig"
            else:
                fase = "klaar" if resultaat == 0 else "mislukt"
        return {"beschikbaar": self.beschikbaar(), "vorige_run": self.vorige_run, "fase": fase}

    def start(self):
        with self.slot:
            toestand = self.toestand()
            if toestand["fase"] == "bezig" or not toestand["beschikbaar"]:
                return 409, toestand
            venv_python = Path("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python = next(
                (map_ / ".venv" / venv_python for map_ in (self.map, ROOT)
                 if (map_ / ".venv" / venv_python).is_file()),
                sys.executable,
            )
            try:
                self.vorige_run = json.loads((self.map / "trace.json").read_text(encoding="utf-8")).get("run_id")
            except (OSError, ValueError, AttributeError):
                self.vorige_run = None
            try:
                self.proces = subprocess.Popen(
                    [str(python), str(ROOT / "council.py"), "--run-dir", str(self.map)],
                    cwd=self.map, stdin=subprocess.DEVNULL,
                )
            except OSError:
                return 500, {"beschikbaar": True, "fase": "mislukt"}
            return 202, {"beschikbaar": True, "fase": "bezig", "vorige_run": self.vorige_run}


def serve(map_, port, *, demo=False):
    raad = None if demo else CouncilRun(map_)
    script = ROOT / ("demo-viewer/replay.js" if demo else "viewer-live.js")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pad = self.path.split("?")[0]
            if pad == "/run-status" and raad is not None:
                return self.stuur_json(200, raad.toestand())
            if pad in ("/", "/index.html"):
                return self.stuur(ROOT / "viewer.html", "text/html; charset=utf-8")
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

        def do_POST(self):
            if raad is None or self.path != "/start-debat":
                return self.send_error(404)
            poort = self.server.server_port
            host = self.headers.get("Host")
            if host not in (f"127.0.0.1:{poort}", f"localhost:{poort}") or self.headers.get("Origin") != f"http://{host}":
                return self.send_error(403)
            if self.headers.get("Content-Length", "0") != "0":
                return self.send_error(400)
            return self.stuur_json(*raad.start())

        def stuur_json(self, status, data):
            return self.stuur_data(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

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
    parser.add_argument("map", nargs="?", type=Path, help="Map met trace.json en verdict.json")
    parser.add_argument("--port", type=int, default=os.getenv("DEMO_VIEWER_PORT", "8104"))
    args = parser.parse_args()
    map_ = args.map.resolve() if args.map is not None else ROOT / "demo-viewer"
    bestanden = ("trace.json", "verdict.json")
    if args.map is None and not any((map_ / naam).exists() for naam in bestanden):
        map_ = ROOT / "demo" / "pitch"
    for naam in bestanden:
        if not (map_ / naam).is_file():
            parser.error(f"Bestand niet gevonden: {map_ / naam}")
    serve(map_, args.port, demo=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--demo"]:
        del sys.argv[1]
        demo_main()
    else:
        main()
