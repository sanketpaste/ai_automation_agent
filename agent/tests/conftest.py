import sys
import socket
import time
import subprocess
from pathlib import Path
from typing import Generator
import pytest

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

@pytest.fixture(scope="session")
def base_url() -> Generator[str, None, None]:
    """
    Auto-starts the dummy app on port 4000 if not already running.
    Provides http://127.0.0.1:4000 to all test specs.
    """
    port: int = 4000
    host: str = "127.0.0.1"
    url: str = f"http://{host}:{port}"
    proc: subprocess.Popen[str] | None = None

    if not is_port_in_use(port, host):
        dummy_server_path: Path = Path(__file__).resolve().parent.parent.parent / "dummy_app" / "server.py"
        proc = subprocess.Popen(
            [sys.executable, str(dummy_server_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        # Wait up to 5s for the server to accept connections
        for _ in range(50):
            if is_port_in_use(port, host):
                break
            time.sleep(0.1)

    yield url

    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
