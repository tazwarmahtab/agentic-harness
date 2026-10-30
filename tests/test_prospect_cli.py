import json
import os
import subprocess
import sys


def test_cli_create_generate_and_reopen(tmp_path):
    document = tmp_path / "notes.txt"
    document.write_text("Synthetic buyer: Example Person")
    env = {**os.environ, "AOS_STATE_DIR": str(tmp_path / "state")}

    def run(*args):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "aos",
                "prospects",
                *args,
                "--venture",
                "netso",
                "--project",
                "demo",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    job = run(
        "create",
        "--prospect",
        "Synthetic Factory",
        "--purpose",
        "Discovery",
        "--files",
        str(document),
    )
    generated = run("generate", "--id", job["id"])
    assert generated["status"] == "needs_review"
    assert run("show", "--id", job["id"])["output_hash"] == generated["output_hash"]
