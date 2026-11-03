#!/usr/bin/env python3
"""Local launcher for Sihha AI.

Starts the FastAPI backend (backend/server.py, port 8001) and the React
frontend (frontend/, port 3000) together, streams both logs with a prefix,
and shuts both down on Ctrl+C.

    python3 server.py --setup     # first run: create backend/.venv, install deps, write .env templates
    python3 server.py             # run backend + frontend
    python3 server.py --backend-only
    python3 server.py --frontend-only

This replaces supervisor (used in the hosted environment) for local dev.
"""
import argparse
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"

BACKEND_PORT = 8001
FRONTEND_PORT = 3000

# emergentintegrations is not on PyPI; it is served from Emergent's index.
EMERGENT_INDEX = "https://d33sy5i8bnduwe.cloudfront.net/simple/"

# Keys backend/server.py and backend/emailer.py read with os.environ[...] at import time.
REQUIRED_BACKEND_KEYS = [
    "MONGO_URL", "DB_NAME", "EMERGENT_LLM_KEY", "JWT_SECRET", "AUDIO_ENCRYPTION_KEY",
    "APP_ENV", "WEBHOOK_CRON_SECRET", "EMERGENT_EMAIL_KEY", "EMAIL_FROM_NAME",
]

COLORS = {"backend": "\033[36m", "frontend": "\033[35m", "launcher": "\033[33m"}
RESET = "\033[0m"


def log(msg, name="launcher"):
    print(f"{COLORS[name]}[{name}]{RESET} {msg}", flush=True)


def read_env(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def fernet_key():
    import base64
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def write_env_templates():
    backend_env = BACKEND / ".env"
    if not backend_env.exists():
        backend_env.write_text(
            "# Fill in the blank values before running.\n"
            "MONGO_URL=\n"
            "DB_NAME=sihha_ai\n"
            "EMERGENT_LLM_KEY=\n"
            "EMERGENT_EMAIL_KEY=\n"
            "EMAIL_FROM_NAME=Sihha AI\n"
            "HF_TOKEN=\n"
            "APP_ENV=development\n"
            f"JWT_SECRET={secrets.token_urlsafe(48)}\n"
            f"AUDIO_ENCRYPTION_KEY={fernet_key()}\n"
            f"WEBHOOK_CRON_SECRET={secrets.token_urlsafe(32)}\n"
            f"CORS_ORIGINS=http://localhost:{FRONTEND_PORT},http://127.0.0.1:{FRONTEND_PORT}\n"
        )
        log(f"wrote {backend_env.relative_to(ROOT)} (fill in MONGO_URL, EMERGENT_LLM_KEY, EMERGENT_EMAIL_KEY)")
    frontend_env = FRONTEND / ".env"
    if not frontend_env.exists():
        frontend_env.write_text(f"REACT_APP_BACKEND_URL=http://localhost:{BACKEND_PORT}\n")
        log(f"wrote {frontend_env.relative_to(ROOT)}")


def venv_python():
    py = VENV / "bin" / "python"
    return str(py) if py.exists() else sys.executable


def js_runner():
    # The project uses yarn only (see CLAUDE.md); npm would write a package-lock.json and drift from yarn.lock.
    return shutil.which("yarn")


def setup():
    write_env_templates()

    if not VENV.exists():
        # The pinned requirements need a recent Python; prefer the newest available.
        base = next((shutil.which(p) for p in ("python3.12", "python3.13", "python3.11") if shutil.which(p)),
                    sys.executable)
        log(f"creating backend/.venv with {base}")
        subprocess.check_call([base, "-m", "venv", str(VENV)])
    py = venv_python()
    subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
    # requirements.txt pins litellm by URL with a #sha256 fragment while emergentintegrations
    # depends on the same URL without it; pip treats those as conflicting, so let
    # emergentintegrations pull litellm in on its own.
    reqs = [line for line in (BACKEND / "requirements.txt").read_text().splitlines()
            if not line.strip().lower().startswith("litellm @")]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(reqs) + "\n")
    try:
        subprocess.check_call([py, "-m", "pip", "install", "-r", f.name,
                               "--extra-index-url", EMERGENT_INDEX])
    finally:
        os.unlink(f.name)

    runner = js_runner()
    if not runner:
        sys.exit("yarn is not installed. Install it (e.g. `brew install node yarn`) and re-run --setup.")
    log("installing frontend deps with yarn")
    subprocess.check_call([runner, "install"], cwd=FRONTEND)
    log("setup complete — run `python3 server.py`")


def check_backend():
    missing = [k for k in REQUIRED_BACKEND_KEYS if not read_env(BACKEND / ".env").get(k)
               and not os.environ.get(k)]
    if missing:
        sys.exit(f"backend/.env is missing values for: {', '.join(missing)}\n"
                 "Run `python3 server.py --setup` to create a template, then fill it in.")
    try:
        subprocess.check_call([venv_python(), "-c", "import fastapi, uvicorn, motor, emergentintegrations"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        sys.exit("Backend dependencies are not installed. Run `python3 server.py --setup`.")


def check_frontend():
    if not js_runner():
        sys.exit("yarn is not installed. Install it (e.g. `brew install node yarn`).")
    if not (FRONTEND / "node_modules").exists():
        sys.exit("Frontend dependencies are not installed. Run `python3 server.py --setup`.")
    if not read_env(FRONTEND / ".env").get("REACT_APP_BACKEND_URL"):
        write_env_templates()


def check_port(port, name):
    import socket
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            sys.exit(f"Port {port} ({name}) is already in use — is another copy running?\n"
                     f"Find it with `lsof -i :{port}` and stop it, then try again.")


def open_in_chrome(url, proc):
    """Wait for the dev server to answer, then open the URL in Chrome (default browser as fallback)."""
    import urllib.request
    import webbrowser
    while proc.poll() is None:
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        return
    if sys.platform == "darwin" and subprocess.call(["open", "-a", "Google Chrome", url]) == 0:
        return
    for name in ("google-chrome", "chrome", "chromium"):
        try:
            webbrowser.get(name).open(url)
            return
        except webbrowser.Error:
            pass
    webbrowser.open(url)


def pipe(proc, name):
    for line in iter(proc.stdout.readline, ""):
        log(line.rstrip(), name)


def start(name, cmd, cwd, env=None):
    log(f"starting: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **(env or {})},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                            start_new_session=True)
    threading.Thread(target=pipe, args=(proc, name), daemon=True).start()
    return proc


def stop(procs):
    for proc in procs:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
    deadline = time.time() + 10
    for proc in procs:
        try:
            proc.wait(timeout=max(0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def main():
    parser = argparse.ArgumentParser(description="Run Sihha AI locally.")
    parser.add_argument("--setup", action="store_true", help="create venv, install deps, write .env templates")
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    parser.add_argument("--no-reload", action="store_true", help="disable uvicorn auto-reload")
    parser.add_argument("--no-browser", action="store_true", help="don't open Chrome when the frontend is ready")
    args = parser.parse_args()

    if args.setup:
        setup()
        return

    run_backend = not args.frontend_only
    run_frontend = not args.backend_only
    if run_backend:
        check_backend()
        check_port(BACKEND_PORT, "backend")
    if run_frontend:
        check_frontend()
        check_port(FRONTEND_PORT, "frontend")

    procs = []
    if run_backend:
        cmd = [venv_python(), "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)]
        if not args.no_reload:
            cmd.append("--reload")
        procs.append(start("backend", cmd, BACKEND))
    if run_frontend:
        frontend = start("frontend", [js_runner(), "start"],
                         FRONTEND, env={"PORT": str(FRONTEND_PORT), "BROWSER": "none"})
        procs.append(frontend)
        if not args.no_browser:
            threading.Thread(target=open_in_chrome, args=(f"http://localhost:{FRONTEND_PORT}", frontend),
                             daemon=True).start()

    if run_backend:
        log(f"API:      http://localhost:{BACKEND_PORT}/api")
    if run_frontend:
        log(f"Frontend: http://localhost:{FRONTEND_PORT}")
    log("press Ctrl+C to stop")

    # Treat `kill` / a closed terminal like Ctrl+C so both servers are always cleaned up.
    def on_term(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGHUP, on_term)

    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        log("a process exited — shutting down the rest")
    except KeyboardInterrupt:
        log("stopping…")
    finally:
        stop(procs)


if __name__ == "__main__":
    main()
