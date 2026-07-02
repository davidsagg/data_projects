"""
Servidor local do dashboard Fica a Dica Premium.
Uso: python dashboard/server.py
Acesse: http://localhost:8766
"""
import json
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
DATA_DIR = ROOT / "data"
PROFILE_PATH = ROOT / "study_plan" / "user_profile.json"
PORT = 8766

_jobs: dict = {}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.command} {self.path} → {args[1] if len(args) > 1 else ''}")

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _load(self, path):
        try:
            return json.loads(Path(path).read_text("utf-8"))
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path).path.rstrip("/") or "/"

        if p == "/api/courses":
            data = self._load(DATA_DIR / "courses.json")
            self._json(data if data is not None else [])
            return

        if p == "/api/study_plan":
            data = self._load(DATA_DIR / "study_plan.json")
            self._json(data if data is not None else {})
            return

        if p == "/api/profile":
            data = self._load(PROFILE_PATH)
            if data is None:
                self._json({"error": "Perfil não encontrado"}, 404)
            else:
                self._json(data)
            return

        if p.startswith("/api/status/"):
            jid = p.split("/")[-1]
            job = _jobs.get(jid)
            self._json(job if job else {"error": "Job não encontrado"}, 200 if job else 404)
            return

        # Static files
        fp = DASHBOARD_DIR / ("index.html" if p == "/" else p.lstrip("/"))
        if fp.exists() and fp.is_file():
            body = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", MIME.get(fp.suffix.lower(), "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": f"Não encontrado: {p}"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n) if n else b""

        if p == "/api/profile":
            try:
                PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
                PROFILE_PATH.write_bytes(body)
                self._json({"ok": True, "message": "Perfil salvo"})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if p == "/api/regenerate":
            try:
                r = subprocess.run(
                    [sys.executable, str(ROOT / "run_planner.py")],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=120,
                )
                plan = self._load(DATA_DIR / "study_plan.json")
                self._json({"ok": r.returncode == 0, "plan": plan, "output": r.stdout[-1000:]})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if p == "/api/rescrape":
            jid = uuid.uuid4().hex[:8]
            _jobs[jid] = {"status": "running", "output": "Iniciando scraper..."}

            def _run(j):
                out = []
                try:
                    for script in ["run_scraper.py", "run_parser.py", "run_planner.py"]:
                        r = subprocess.run(
                            [sys.executable, str(ROOT / script)],
                            cwd=str(ROOT), capture_output=True, text=True, timeout=600,
                        )
                        out.append(f"--- {script} ---\n{r.stdout}\n{r.stderr}")
                        if r.returncode != 0:
                            _jobs[j] = {"status": "error", "output": "\n".join(out)[-3000:]}
                            return
                    _jobs[j] = {"status": "done", "output": "\n".join(out)[-3000:]}
                except Exception as e:
                    _jobs[j] = {"status": "error", "output": str(e)}

            threading.Thread(target=_run, args=(jid,), daemon=True).start()
            self._json({"job_id": jid, "status": "running"})
            return

        self._json({"error": f"Rota não encontrada: {p}"}, 404)


if __name__ == "__main__":
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"\n  🎸  Fica a Dica Dashboard")
    print(f"  📡  http://localhost:{PORT}")
    print("  ─────────────────────────")
    print("  Ctrl+C para parar\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  🛑  Encerrado.")
        srv.shutdown()
