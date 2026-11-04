"""Mocked regressions: these tests must never execute shell commands."""

from unittest.mock import Mock, patch

import pytest

from aos.tools import ToolGateway


@pytest.mark.parametrize(
    "command",
    [
        "chmod 777 /",
        "chmod -R 777 '/'",
        "chmod u+rwx /",
        "chown root /",
        "chown -R root:root '/'",
        "/bin/chmod 777 //",
        "mv file /",
        "mv file '/' -f",
        "mv -t / file",
        "mv -t/ file",
        "mv --target-directory / file",
        "mv --target-directory=/ file",
        "mv -- file '/'",
        "echo ready; chmod 777 '/'",
        "chmod 777 /tmp/..",
    ],
)
def test_root_mutations_never_reach_subprocess(command: str) -> None:
    with patch("aos.tools.subprocess.run") as runner:
        result = ToolGateway()._exec_shell({"command": command})
    assert result["ok"] is False
    assert "Blocked" in result["error"]
    runner.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [
        "chmod 600 /tmp/example",
        "mv /tmp/source /tmp/destination",
        "mv -t /tmp/destination /tmp/source",
        "echo hello",
    ],
)
def test_non_root_examples_retain_execution_path(command: str) -> None:
    response = Mock(returncode=0, stdout="fixture", stderr="")
    with patch("aos.tools.subprocess.run", return_value=response) as runner:
        result = ToolGateway()._exec_shell({"command": command})
    assert result["ok"] is True
    runner.assert_called_once()
