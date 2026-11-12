"""Run the unit tests with external data and model requests blocked.

Usage:
    uv run python tests/run_offline.py

The guard replaces socket connections and common HTTP entry points with
fail-fast stubs. The unit tests use synthetic data, so no real request should
be attempted. A deliberate probe confirms the guard is active.
"""

import os
from pathlib import Path
import socket
import sys
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["F1LAB_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"


class OfflineBlocked(RuntimeError):
    pass


_original_socket = socket.socket


class GuardedSocket(_original_socket):
    def connect(self, *args, **kwargs):
        raise OfflineBlocked("External network access is blocked during offline tests")

    def connect_ex(self, *args, **kwargs):
        raise OfflineBlocked("External network access is blocked during offline tests")


socket.socket = GuardedSocket


def blocked_getaddrinfo(*args, **kwargs):
    raise OfflineBlocked("External name resolution is blocked during offline tests")


socket.getaddrinfo = blocked_getaddrinfo


def blocked_urlopen(*args, **kwargs):
    raise OfflineBlocked("External HTTP access is blocked during offline tests")


urllib.request.urlopen = blocked_urlopen

try:
    import requests

    def blocked_request(self, *args, **kwargs):
        raise OfflineBlocked("External HTTP access is blocked during offline tests")

    requests.Session.request = blocked_request
except ImportError:
    pass


def main():
    try:
        socket.create_connection(("example.com", 80), timeout=1)
    except OfflineBlocked:
        print("Network guard active: external data and model requests will fail fast.")
    else:
        raise SystemExit("Network guard failed: a connection was allowed.")

    suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
