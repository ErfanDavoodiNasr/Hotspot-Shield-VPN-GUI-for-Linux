"""Hardened subprocess runner."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from hotspotshield_gui.utils.errors import (
    AppError,
    CliNotFoundError,
    CliPermissionError,
    CliTimeoutError,
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

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


@dataclass
class ProcessRunner:
    """Run external commands safely (no shell)."""

    env_overrides: Mapping[str, str] = field(default_factory=dict)
    default_timeout: float = DEFAULT_TIMEOUT
    path_prepend: Sequence[str] = field(default_factory=tuple)

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float | None = None,
        input_text: str | None = None,
        cwd: str | Path | None = None,
        check: bool = False,
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
        # Avoid leaking locale surprises; keep LANG if present.
        env.setdefault("LC_ALL", "C.UTF-8")

        logger.debug("Running command: %s", list(argv))
        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 — argv is a list, no shell
                list(argv),
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                env=env,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CliNotFoundError(argv[0]) from exc
        except PermissionError as exc:
            raise CliPermissionError(argv[0]) from exc
        except subprocess.TimeoutExpired as exc:
            stdout = _decode(exc.stdout)
            stderr = _decode(exc.stderr)
            duration = time.monotonic() - started
            logger.warning("Command timed out after %.1fs: %s", timeout, argv)
            # Best-effort cleanup of any lingering children is handled by
            # subprocess.run killing the process group on timeout in py3.11+,
            # and the TimeoutExpired path already terminates the process.
            result = CommandResult(
                argv=tuple(argv),
                returncode=-1,
                stdout=_truncate(stdout),
                stderr=_truncate(stderr),
                duration_seconds=duration,
                timed_out=True,
            )
            raise CliTimeoutError(" ".join(argv)) from None
        except OSError as exc:
            raise AppError(
                "Unable to run Hotspot Shield command.",
                technical=str(exc),
            ) from exc

        duration = time.monotonic() - started
        result = CommandResult(
            argv=tuple(argv),
            returncode=completed.returncode,
            stdout=_truncate(completed.stdout or ""),
            stderr=_truncate(completed.stderr or ""),
            duration_seconds=duration,
        )
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
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            pass
        proc.kill()
        proc.wait(timeout=grace)
    except ProcessLookupError:
        return
    except OSError:
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except OSError:
            return


def _decode(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _truncate(text: str, limit: int = MAX_OUTPUT_BYTES) -> str:
    if len(text.encode("utf-8", errors="replace")) <= limit:
        return text
    return text[:limit] + "\n…[truncated]…"
