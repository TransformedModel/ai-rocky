"""App package. ``get_timing_logger`` is wired to stderr so Railway always shows timing lines."""

from __future__ import annotations

import logging
import sys

_TIMING_LOGGER_NAME = "omnivoice_chat.timing"


def get_timing_logger() -> logging.Logger:
    """Return a logger that writes to **stderr** (not only via uvicorn's root config)."""
    log = logging.getLogger(_TIMING_LOGGER_NAME)
    log.setLevel(logging.INFO)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.propagate = False
    return log
