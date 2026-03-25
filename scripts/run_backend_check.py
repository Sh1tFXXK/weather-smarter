from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backend_env import build_backend_env


def main() -> None:
    project_root = PROJECT_ROOT
    python_exe = project_root / ".pyembed" / "python.exe"
    log_path = project_root / "backend_server.log"

    with log_path.open("ab") as log_file:
        server = subprocess.Popen(
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
        )

    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            if server.poll() is not None:
                raise RuntimeError(f"uvicorn exited early with code {server.returncode}")
            try:
                with urlopen("http://127.0.0.1:8000/docs", timeout=2) as response:
                    if response.status == 200:
                        break
            except URLError:
                time.sleep(1)
        else:
            raise RuntimeError("uvicorn did not become ready within 20s")

        check = subprocess.run(
            [str(python_exe), "scripts/check_backend_http.py"],
            cwd=project_root,
            env=build_backend_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
        sys.stdout.write(check.stdout)
        sys.stderr.write(check.stderr)
        if check.returncode != 0:
            raise RuntimeError("backend HTTP check failed")
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"ERROR {exc}")
        sys.exit(1)
