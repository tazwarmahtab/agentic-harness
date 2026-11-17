"""Mocked regressions: these tests must never execute shell commands.

Battery ported from PR #22 (fix/root-mutation-guard-20261105). One case is
adapted: PR #22's guard is root-only, so it allows "chmod 600 /tmp/example".
The guard on main deliberately blocks chmod and chown on any absolute path
(merged in PR #29), so that case is asserted blocked here, as a documented
policy divergence, in test_absolute_chmod_policy_divergence below.
"""

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
        "mv -ft'/' file",
        "mv -vft'//' file",
        "mv -nvt'/..' file",
        "/usr/bin/mv -it'/' file",
        "mv --target-directory / file",
        "mv --target-directory=/ file",
        "mv -- file '/'",
        "echo ready; chmod 777 '/'",
        "chmod 777 /..",
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
        "mv /tmp/source /tmp/destination",
        "mv -t /tmp/destination /tmp/source",
        "mv -ft'/tmp/destination' /tmp/source",
        "mv -vft'/tmp/destination' /tmp/source",
        "echo hello",
    ],
)
def test_non_root_examples_retain_execution_path(command: str) -> None:
    response = Mock(returncode=0, stdout="fixture", stderr="")
    with patch("aos.tools.subprocess.run", return_value=response) as runner:
        result = ToolGateway()._exec_shell({"command": command})
    assert result["ok"] is True
    runner.assert_called_once()


def test_absolute_chmod_policy_divergence() -> None:
    # PR #22 allows this (root-only guard). Main's merged policy blocks
    # chmod on any absolute path, /tmp included. Recorded as a deliberate
    # divergence for Taz to reverse if he prefers the narrower rule.
    with patch("aos.tools.subprocess.run") as runner:
        result = ToolGateway()._exec_shell({"command": "chmod 600 /tmp/example"})
    assert result["ok"] is False
    assert "Blocked" in result["error"]
    runner.assert_not_called()
