"""App package. ``get_timing_logger`` lives here so deploys always ship it with the package."""

from __future__ import annotations

import logging

_TIMING_LOGGER_NAME = "omnivoice_chat.timing"


def get_timing_logger() -> logging.Logger:
    log = logging.getLogger(_TIMING_LOGGER_NAME)
    log.setLevel(logging.INFO)
    return log
