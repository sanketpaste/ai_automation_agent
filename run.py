import os
import sys
import subprocess
import signal
import time
from pathlib import Path
from typing import List

reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
if callable(reconfigure_fn):
    try:
        reconfigure_fn(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR: Path = Path(__file__).resolve().parent

def get_env() -> dict[str, str]:
    """Returns environment with PYTHONPATH set to project root."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT_DIR)
    return env

def run_dummy() -> None:
    """Starts the dummy app on port 4000."""
    print("[TaskRunner] Starting Dummy App on http://127.0.0.1:4000 ...")
    cmd: List[str] = [sys.executable, str(ROOT_DIR / "dummy_app" / "server.py")]
    subprocess.run(cmd, env=get_env())

def run_agent() -> None:
    """Starts the agent server on http://127.0.0.1:3000."""
    print("[TaskRunner] Starting Agent Server on http://127.0.0.1:3000 ...")
    cmd: List[str] = [sys.executable, str(ROOT_DIR / "agent" / "server.py")]
    subprocess.run(cmd, env=get_env())

def run_dev() -> None:
    """Starts both Dummy App and Agent Server concurrently."""
    print("[TaskRunner] Launching development environment (Dummy App + Agent Server)...")
    env = get_env()
    p_dummy = subprocess.Popen([sys.executable, str(ROOT_DIR / "dummy_app" / "server.py")], env=env)
    p_agent = subprocess.Popen([sys.executable, str(ROOT_DIR / "agent" / "server.py")], env=env)

    print("----------------------------------------------------------------------")
    print("Dummy App running on:   http://127.0.0.1:4000")
    print("Agent Chat running on:  http://127.0.0.1:3000/chat")
    print("Press Ctrl+C to terminate both servers.")
    print("----------------------------------------------------------------------")

    try:
        while True:
            time.sleep(1)
            if p_dummy.poll() is not None or p_agent.poll() is not None:
                break
    except KeyboardInterrupt:
        print("\n[TaskRunner] Shutting down servers...")
    finally:
        for p in (p_dummy, p_agent):
            if p and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2)
                except Exception:
                    p.kill()

def run_test() -> None:
    """Runs the standalone pytest flow specifications."""
    print("[TaskRunner] Running pytest flow specifications...")
    cmd: List[str] = [sys.executable, "-m", "pytest", str(ROOT_DIR / "agent" / "tests")]
    ret = subprocess.run(cmd)
    sys.exit(ret.returncode)

def print_help() -> None:
    print("Usage: python run.py [command]")
    print("Available commands:")
    print("  dummy   Start the dummy web app on http://127.0.0.1:4000")
    print("  agent   Start the agent server on http://127.0.0.1:3000")
    print("  dev     Start both servers together concurrently")
    print("  test    Run standalone pytest flow specifications")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    command: str = sys.argv[1].lower()
    if command == "dummy":
        run_dummy()
    elif command == "agent":
        run_agent()
    elif command == "dev":
        run_dev()
    elif command == "test":
        run_test()
    else:
        print(f"Unknown command: '{command}'")
        print_help()
        sys.exit(1)
