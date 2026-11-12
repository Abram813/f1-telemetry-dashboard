"""CI smoke test: start the README command, use the app, then stop it.

This script is intentionally cross-platform. It runs the exact launch command
from the README (``uv run streamlit run app.py``) from the repository root,
waits for Streamlit's health endpoint, runs the AppTest acceptance checks, and
then asks the process group to shut down. It fails if shutdown needs a forced
kill or leaves the port open.
"""

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PORT = 8501
HEALTH = f"http://127.0.0.1:{PORT}/_stcore/health"


def port_is_open():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


def wait_until_ready(process, log_path, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            log = Path(log_path).read_text(errors="replace")
            raise RuntimeError(f"Streamlit exited early ({process.returncode}).\n{log}")
        try:
            with urllib.request.urlopen(HEALTH, timeout=2) as response:
                if response.status == 200 and response.read().strip() == b"ok":
                    return
        except Exception:
            time.sleep(1)
    log = Path(log_path).read_text(errors="replace")
    raise TimeoutError(f"Streamlit did not become healthy within {timeout}s.\n{log}")


def stop(process, timeout=30):
    """Return (graceful, returncode). A forced kill is not graceful."""
    if process.poll() is not None:
        return True, process.returncode
    if os.name == "nt":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGINT)
    try:
        process.wait(timeout=timeout)
        graceful = True
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        process.wait(timeout=10)
        graceful = False
    deadline = time.time() + 10
    while time.time() < deadline and port_is_open():
        time.sleep(0.5)
    return graceful, process.returncode


def main():
    if port_is_open():
        raise SystemExit(f"Port {PORT} is already in use; stop the other process first.")

    log_file = tempfile.NamedTemporaryFile(prefix="f1-telemetry-streamlit-", suffix=".log",
                                           delete=False)
    log_path = log_file.name
    log_file.close()

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    with open(log_path, "w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            ["uv", "run", "streamlit", "run", "app.py"],
            cwd=ROOT, env=env, stdout=log_handle, stderr=subprocess.STDOUT, **kwargs,
        )
        try:
            wait_until_ready(process, log_path)
            print("PASS: Streamlit started with `uv run streamlit run app.py` and is healthy.")
            result = subprocess.run(
                ["uv", "run", "python", "tests/integration_smoke.py"],
                cwd=ROOT, check=False,
            )
            if result.returncode != 0:
                raise RuntimeError("AppTest acceptance checks failed.")
        finally:
            graceful, returncode = stop(process)
            log = Path(log_path).read_text(errors="replace")
            if not graceful:
                print(log)
            print(f"Streamlit shutdown: graceful={graceful}, returncode={returncode}, "
                  f"port_open={port_is_open()}")

    if not graceful:
        raise SystemExit("Streamlit required a forced kill, so shutdown was not clean.")
    if port_is_open():
        raise SystemExit("Streamlit left the health port open after shutdown.")
    print("PASS: app started, completed the acceptance action, and shut down cleanly.")


if __name__ == "__main__":
    main()
