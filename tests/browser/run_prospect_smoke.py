"""Launch both real apps and run synthetic browser checks in one process environment."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aos-browser-") as state:
        env = {
            **os.environ,
            "AOS_API_TOKEN": "synthetic-browser-token",
            "AOS_STATE_DIR": state,
            "AOS_PROSPECT_MODEL_ENABLED": "0",
            "AOS_ENGINE_URL": "http://127.0.0.1:7711",
        }
        processes = []
        with open(Path(state) / "servers.log", "w") as log:
            try:
                for module, port in [
                    ("aos.api:app", "7711"),
                    ("odysseus.server:app", "7777"),
                ]:
                    processes.append(
                        subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "uvicorn",
                                module,
                                "--host",
                                "127.0.0.1",
                                "--port",
                                port,
                            ],
                            env=env,
                            stdout=log,
                            stderr=log,
                        )
                    )
                for port in (7711, 7777):
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            with urllib.request.urlopen(
                                f"http://127.0.0.1:{port}/health", timeout=1
                            ):
                                break
                        except (urllib.error.URLError, OSError):
                            if time.monotonic() > deadline:
                                raise RuntimeError(
                                    Path(state, "servers.log").read_text()
                                ) from None
                            time.sleep(0.1)
                subprocess.run(
                    ["node", "tests/browser/prospect-smoke.cjs"],
                    check=True,
                    env=env,
                    timeout=90,
                )
            finally:
                for process in processes:
                    process.terminate()
                for process in processes:
                    process.wait(timeout=10)


if __name__ == "__main__":
    main()
