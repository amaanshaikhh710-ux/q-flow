"""Q-FLOW — Master Runner Script.

Orchestrates both the FastAPI backend and React frontend services locally:
1. Runs database setup/seeding.
2. Launches FastAPI backend on http://localhost:8000.
3. Launches Frontend on http://localhost:5173.
4. Monitors both processes and provides unified logs.
"""

import os
import sys
import subprocess
import time
import signal
import shutil


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Determine Python executable
candidate_venv = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
VENV_PYTHON = sys.executable
if os.path.exists(candidate_venv):
    try:
        res = subprocess.run([candidate_venv, "--version"], capture_output=True, text=True)
        if res.returncode == 0:
            VENV_PYTHON = candidate_venv
    except Exception:
        pass



def init_db():
    print("\n==========================================")
    print("[1/3] Initializing Q-FLOW Database...")
    print("==========================================")
    init_script = os.path.join(BACKEND_DIR, "scripts", "init_db.py")
    res = subprocess.run([VENV_PYTHON, init_script], cwd=BACKEND_DIR)
    if res.returncode != 0:
        print("[WARNING] Database initialization exited with non-zero status.")
    else:
        print("[OK] Database ready and demo data seeded.")


def start_services():
    print("\n==========================================")
    print("[2/3] Starting Backend & Frontend Services...")
    print("==========================================")

    # Backend command
    backend_cmd = [
        VENV_PYTHON,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    print(f"Starting Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(backend_cmd, cwd=BACKEND_DIR)

    # Frontend command: use Vite if npx is available, else fallback to serve_spa.py
    npx_exe = shutil.which("npx") or shutil.which("npx.cmd")
    if npx_exe:
        frontend_cmd = [npx_exe, "vite", "--port", "5173"]
    else:
        frontend_script = os.path.join(FRONTEND_DIR, "scripts", "serve_spa.py")
        frontend_cmd = [VENV_PYTHON, frontend_script]
    print(f"Starting Frontend on http://localhost:5173 ...")
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=FRONTEND_DIR)


    print("\n==========================================")
    print("[3/3] Q-FLOW is Live!")
    print("==========================================")
    print("  * Frontend Web App:     http://localhost:5173")
    print("  * Backend API:          http://localhost:8000")
    print("  * Interactive API Docs: http://localhost:8000/docs")
    print("  * Health Probe:         http://localhost:8000/health")
    print("------------------------------------------")
    print("Demo Logins:")
    print("  * Patient:      patient@qflow.com / password123")
    print("  * Receptionist: receptionist1@cityhealth.com / password123")
    print("  * Staff:        staff@qflow.com / password123")
    print("==========================================\n")
    print("Press Ctrl+C to terminate both servers.\n")

    try:
        while True:
            time.sleep(1)
            # Check if any process terminated unexpectedly
            if backend_proc.poll() is not None:
                print(f"[Backend Error] Backend process terminated with code {backend_proc.returncode}")
                break
            if frontend_proc.poll() is not None:
                print(f"[Frontend Error] Frontend process terminated with code {frontend_proc.returncode}")
                break
    except KeyboardInterrupt:
        print("\nShutting down Q-FLOW services...")
    finally:
        for proc in [backend_proc, frontend_proc]:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        print("All services stopped.")


if __name__ == "__main__":
    init_db()
    start_services()
