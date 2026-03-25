from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backend_env import build_backend_env


def _find_listener_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    pids: list[int] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("TCP"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        state = parts[3]
        if state != "LISTENING":
            continue
        if not (local_addr.endswith(f":{port}") or local_addr.endswith(f"]:{port}")):
            continue
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        if pid > 0 and pid not in pids:
            pids.append(pid)
    return pids


def _wait_until_port_free(port: int, timeout_s: float = 10) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _find_listener_pids(port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"port {port} still occupied after waiting")


def _terminate_listener_pids(port: int) -> None:
    for pid in _find_listener_pids(port):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    _wait_until_port_free(port)


def _read_status_payload(timeout_s: float = 5.0) -> dict:
    with urlopen("http://127.0.0.1:8000/api/v1/status", timeout=timeout_s) as response:
        import json
        return json.loads(response.read().decode("utf-8"))


def _wait_until_llm_ready(timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_error = "backend not ready"
    while time.time() < deadline:
        try:
            payload = _read_status_payload(timeout_s=5.0)
            llm = payload.get("llm") or {}
            if llm.get("available"):
                return
            last_error = f"llm unavailable: {llm.get('reason') or 'unknown reason'}"
        except URLError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(last_error)


def main() -> None:
    project_root = PROJECT_ROOT
    python_exe = project_root / ".pyembed" / "python.exe"
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"backend-{timestamp}.log"
    latest_log_path = project_root / "backend_server.log"
    _terminate_listener_pids(8000)

    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            [
                str(python_exe),
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=project_root,
            env=build_backend_env(),
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    try:
        latest_log_path.write_text(str(log_path), encoding="utf-8")
    except OSError:
        pass

    try:
        if build_backend_env().get("EXPECT_LLM", "1") in {"1", "true", "TRUE"}:
            _wait_until_llm_ready(timeout_s=45.0)
    except Exception:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/F", "/T"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        raise

    print(process.pid)


if __name__ == "__main__":
    main()
