"""Hardened subprocess runner with cancellable process groups."""

from __future__ import annotations

import logging
import os
import signal
import subprocess  # nosec B404
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from hotspotshield_gui.utils.errors import (
    AppError,
    CliNotFoundError,
    CliPermissionError,
    CliTimeoutError,
    OperationCancelledError,
)

logger = logging.getLogger("hotspotshield_gui.cli.process_runner")

DEFAULT_TIMEOUT = 60.0
MAX_OUTPUT_BYTES = 2_000_000


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.cancelled

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


@dataclass
class ProcessRunner:
    """Run external commands safely (no shell), with optional cancel."""

    env_overrides: Mapping[str, str] = field(default_factory=dict)
    default_timeout: float = DEFAULT_TIMEOUT
    path_prepend: Sequence[str] = field(default_factory=tuple)
    poll_interval: float = 0.1

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float | None = None,
        input_text: str | None = None,
        cwd: str | Path | None = None,
        check: bool = False,
        cancel_event: threading.Event | None = None,
    ) -> CommandResult:
        if not argv:
            raise ValueError("argv must not be empty")
        if any(not isinstance(part, str) for part in argv):
            raise TypeError("argv must contain only strings")

        timeout = self.default_timeout if timeout is None else timeout
        env = os.environ.copy()
        if self.path_prepend:
            env["PATH"] = os.pathsep.join([*self.path_prepend, env.get("PATH", "")])
        env.update(self.env_overrides)
        env.setdefault("LC_ALL", "C.UTF-8")

        if cancel_event is not None and cancel_event.is_set():
            raise OperationCancelledError(" ".join(argv))

        logger.debug("Running command: %s", list(argv))
        started = time.monotonic()
        try:
            proc = subprocess.Popen(  # noqa: S603  # nosec B603
                list(argv),
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(cwd) if cwd else None,
                env=env,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise CliNotFoundError(argv[0]) from exc
        except PermissionError as exc:
            raise CliPermissionError(argv[0]) from exc
        except OSError as exc:
            raise AppError(
                "Unable to run Hotspot Shield command.",
                technical=str(exc),
            ) from exc

        cancelled = False
        timed_out = False
        try:
            if input_text is not None and proc.stdin is not None:
                try:
                    proc.stdin.write(input_text)
                except BrokenPipeError:
                    pass
                finally:
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass
                    # Prevent communicate() from flushing an already-closed stdin.
                    proc.stdin = None

            deadline = time.monotonic() + timeout
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    _terminate_group(proc)
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    _terminate_group(proc)
                    break
                try:
                    proc.wait(timeout=min(self.poll_interval, max(0.01, remaining)))
                    break
                except subprocess.TimeoutExpired:
                    continue

            try:
                stdout, stderr = proc.communicate(timeout=2.0)
            except ValueError:
                # Race: stdin already closed / pipes torn down after terminate.
                stdout, stderr = "", ""
                try:
                    if proc.stdout is not None:
                        stdout = proc.stdout.read() or ""
                    if proc.stderr is not None:
                        stderr = proc.stderr.read() or ""
                except (OSError, ValueError):
                    pass
                if proc.poll() is None:
                    _terminate_group(proc)
        except Exception:
            _terminate_group(proc)
            raise

        duration = time.monotonic() - started
        result = CommandResult(
            argv=tuple(argv),
            returncode=-1 if (timed_out or cancelled) else int(proc.returncode or 0),
            stdout=_truncate(stdout or ""),
            stderr=_truncate(stderr or ""),
            duration_seconds=duration,
            timed_out=timed_out,
            cancelled=cancelled,
        )
        if cancelled:
            raise OperationCancelledError(" ".join(argv))
        if timed_out:
            logger.warning("Command timed out after %.1fs: %s", timeout, argv)
            raise CliTimeoutError(" ".join(argv))
        if check and not result.ok:
            raise AppError(
                "Hotspot Shield returned an unexpected response.",
                technical=result.combined or f"exit {result.returncode}",
            )
        return result

    def which(self, name: str) -> str | None:
        path = os.environ.get("PATH", "")
        if self.path_prepend:
            path = os.pathsep.join([*self.path_prepend, path])
        for directory in path.split(os.pathsep):
            candidate = Path(directory) / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None


def terminate_process(proc: subprocess.Popen[str], *, grace: float = 2.0) -> None:
    """Terminate a process, escalating to SIGKILL if needed."""
    _terminate_group(proc, grace=grace)


def _terminate_group(proc: subprocess.Popen[str], *, grace: float = 2.0) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except OSError:
            return
    try:
        proc.wait(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            return
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        return


def _truncate(text: str, limit: int = MAX_OUTPUT_BYTES) -> str:
    if len(text.encode("utf-8", errors="replace")) <= limit:
        return text
    return text[:limit] + "\n…[truncated]…"
