"""Process runner hardening tests."""

from __future__ import annotations

import sys

import pytest

from hotspotshield_gui.cli.process_runner import ProcessRunner
from hotspotshield_gui.utils.errors import CliNotFoundError, CliTimeoutError


def test_runner_captures_output() -> None:
    runner = ProcessRunner()
    result = runner.run([sys.executable, "-c", "print('hello')"], timeout=10)
    assert result.ok
    assert "hello" in result.stdout


def test_runner_timeout() -> None:
    runner = ProcessRunner()
    with pytest.raises(CliTimeoutError):
        runner.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)


def test_runner_missing_executable() -> None:
    runner = ProcessRunner()
    with pytest.raises(CliNotFoundError):
        runner.run(["definitely-not-a-real-binary-xyz"], timeout=5)


def test_runner_rejects_non_string_argv() -> None:
    runner = ProcessRunner()
    with pytest.raises(TypeError):
        runner.run(["echo", 1])  # type: ignore[list-item]


def test_no_shell_metacharacter_execution(tmp_path) -> None:
    # Ensure we do not invoke a shell: a single argument containing ';' should not run two commands.
    runner = ProcessRunner()
    marker = tmp_path / "pwned"
    result = runner.run(
        [sys.executable, "-c", f"import pathlib; pathlib.Path({str(marker)!r}).write_text('x')"],
        timeout=10,
    )
    # Control: direct write works
    assert result.ok
    marker.unlink()
    # Passing shell syntax as a single argv to /bin/echo must not create the file via shell.
    runner.run(["/bin/echo", f"touch {marker}"], timeout=5)
    assert not marker.exists()
