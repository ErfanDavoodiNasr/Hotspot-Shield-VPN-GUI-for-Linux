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


def test_runner_cancel_interrupts_sleep() -> None:
    import threading
    import time

    from hotspotshield_gui.utils.errors import OperationCancelledError

    runner = ProcessRunner(poll_interval=0.05)
    cancel = threading.Event()

    def _cancel_soon() -> None:
        time.sleep(0.15)
        cancel.set()

    threading.Thread(target=_cancel_soon, daemon=True).start()
    started = time.monotonic()
    with pytest.raises(OperationCancelledError):
        runner.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=10, cancel_event=cancel)
    assert time.monotonic() - started < 3.0


def test_no_shell_metacharacter_execution(tmp_path) -> None:
    runner = ProcessRunner()
    marker = tmp_path / "pwned"
    result = runner.run(
        [sys.executable, "-c", f"import pathlib; pathlib.Path({str(marker)!r}).write_text('x')"],
        timeout=10,
    )
    assert result.ok
    marker.unlink()
    runner.run(["/bin/echo", f"touch {marker}"], timeout=5)
    assert not marker.exists()
