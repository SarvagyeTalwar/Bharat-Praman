"""Start the Bharat Praman API, RTI server and frontend on any machine.

Usage:
    python start_all.py

Environment overrides:
    BP_HOST=0.0.0.0  API_PORT=8000  RTI_PORT=8001  WEB_PORT=5500
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = os.getenv("BP_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
RTI_PORT = int(os.getenv("RTI_PORT", "8001"))
WEB_PORT = int(os.getenv("WEB_PORT", "5500"))


def check_deps():
    missing = []
    for mod in ("fastapi", "uvicorn", "neo4j", "dotenv", "google.genai", "pydantic"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        print("Missing Python packages:", ", ".join(missing))
        print("Install them with: python -m pip install -r requirements.txt")
        raise SystemExit(1)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def wait_for_api(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def main():
    check_deps()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    procs = [
        ("API", API_PORT, [sys.executable, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(API_PORT)]),
        ("RTI", RTI_PORT, [sys.executable, "-m", "uvicorn", "rti.server:app", "--host", HOST, "--port", str(RTI_PORT)]),
        ("WEB", WEB_PORT, [sys.executable, "-m", "http.server", str(WEB_PORT), "--bind", HOST]),
    ]

    started = []
    try:
        for name, port, cmd in procs:
            print(f"Starting {name} on {HOST}:{port} ...")
            started.append((name, subprocess.Popen(cmd, cwd=ROOT, env=env)))

        if not wait_for_api():
            print("API did not become healthy in 30s. Check the terminal output above.")
            raise SystemExit(1)

        host = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
        ip = lan_ip()
        print("\nBharat Praman is running:")
        print(f"  Local:  http://{host}:{WEB_PORT}/graphdashboard2.html")
        print(f"  LAN:    http://{ip}:{WEB_PORT}/graphdashboard2.html")
        print(f"  API:    http://{host}:{API_PORT}/docs")
        print(f"  RTI:    http://{host}:{RTI_PORT}/rti-page")
        print("\nPress Ctrl+C to stop all services.")

        while True:
            for name, proc in started:
                if proc.poll() is not None:
                    print(f"{name} stopped (exit {proc.returncode}).")
                    raise SystemExit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping services ...")
    finally:
        for name, proc in started:
            if proc.poll() is None:
                proc.terminate()
        for name, proc in started:
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
