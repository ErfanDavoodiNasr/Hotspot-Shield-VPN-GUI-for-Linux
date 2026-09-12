"""Logging helpers with secret redaction."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from hotspotshield_gui.security.redaction import redact_text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_text(original)


def default_log_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".local" / "state"
    path = base / "hotspotshield-gui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(level: str | int = "INFO", *, log_to_file: bool = True) -> logging.Logger:
    logger = logging.getLogger("hotspotshield_gui")
    if logger.handlers:
        return logger

    if isinstance(level, str):
        numeric = getattr(logging, level.upper(), logging.INFO)
    else:
        numeric = level
    logger.setLevel(numeric)

    formatter = RedactingFormatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    stream.setLevel(numeric)
    logger.addHandler(stream)

    if log_to_file:
        try:
            file_path = default_log_dir() / "app.log"
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(numeric)
            logger.addHandler(file_handler)
        except OSError:
            logger.warning("Unable to open log file; continuing with console logging only")

    logger.debug("Logging initialized at level %s", logging.getLevelName(numeric))
    return logger
