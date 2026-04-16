from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
_warned_missing_life: bool = False
_warned_missing_speech: bool = False

# backend/app -> omnivoice-chat
_ROCKY_DIR = Path(__file__).resolve().parents[2] / "Rocky"
_LIFE_PATH = _ROCKY_DIR / "Rocky-Life.md"
_SPEECH_PATH = _ROCKY_DIR / "Rocky-Speech-Style.md"

# path key -> (mtime_or_none_if_missing, text)
_cache: dict[str, tuple[float | None, str]] = {}


def _max_chars_per_file() -> int:
    try:
        return max(1_000, int(os.getenv("ROCKY_PROMPT_MAX_CHARS", "12000")))
    except ValueError:
        return 12_000


def _mtime(path: Path) -> float | None:
    if not path.is_file():
        return None
    return path.stat().st_mtime


def _read_file_capped(path: Path) -> str:
    if not path.is_file():
        return ""
    raw = path.read_text(encoding="utf-8").strip()
    cap = _max_chars_per_file()
    if len(raw) > cap:
        return raw[:cap] + "\n\n[Truncated for ROCKY_PROMPT_MAX_CHARS]"
    return raw


def _cached_text(cache_key: str, path: Path) -> str:
    mtime = _mtime(path)
    hit = _cache.get(cache_key)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    text = _read_file_capped(path)
    _cache[cache_key] = (mtime, text)
    return text


def get_rocky_life_text() -> str:
    """Backstory / personality from Rocky-Life.md; reloads when mtime changes."""
    global _warned_missing_life
    text = _cached_text("life", _LIFE_PATH)
    if not text and not _LIFE_PATH.is_file() and not _warned_missing_life:
        logger.warning(
            "Rocky-Life.md not found at %s (cwd=%s); Eridian backstory will not be in the prompt.",
            _LIFE_PATH,
            os.getcwd(),
        )
        _warned_missing_life = True
    return text


def get_rocky_speech_style_text() -> str:
    """Dialogue style from Rocky-Speech-Style.md; reloads when mtime changes."""
    global _warned_missing_speech
    text = _cached_text("speech", _SPEECH_PATH)
    if not text and not _SPEECH_PATH.is_file() and not _warned_missing_speech:
        logger.warning(
            "Rocky-Speech-Style.md not found at %s (cwd=%s); speech-style block omitted.",
            _SPEECH_PATH,
            os.getcwd(),
        )
        _warned_missing_speech = True
    return text
