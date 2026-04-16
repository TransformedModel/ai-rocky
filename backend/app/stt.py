from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path


class SttError(RuntimeError):
    pass


@dataclass(frozen=True)
class SttResult:
    text: str
    language: str | None = None


_whisper_lock = threading.Lock()
_whisper_model = None
_whisper_model_name: str | None = None
# openai-whisper can hit unsupported sparse ops on MPS (SparseMPS); fall back once.
_whisper_mps_broken: bool = False


def _is_mps_sparse_failure(msg: str) -> bool:
    return "SparseMPS" in msg or "_sparse_coo_tensor" in msg


def _clear_whisper_model() -> None:
    global _whisper_model, _whisper_model_name
    with _whisper_lock:
        _whisper_model = None
        _whisper_model_name = None


def _pick_whisper_device() -> str | None:
    global _whisper_mps_broken
    if _whisper_mps_broken:
        return "cpu"

    forced = (os.getenv("WHISPER_DEVICE") or "").strip().lower()
    if forced in ("cpu", "cuda", "mps"):
        return forced
    if forced:
        return os.getenv("WHISPER_DEVICE")

    # Do not auto-pick MPS: Whisper's decode path can call ops that are not implemented
    # on SparseMPS. Let whisper.load_model use cuda when available, else CPU.
    return None


def get_whisper_model():
    global _whisper_model, _whisper_model_name
    model_name = os.getenv("WHISPER_MODEL", "base")
    if _whisper_model is not None and _whisper_model_name == model_name:
        return _whisper_model

    with _whisper_lock:
        model_name = os.getenv("WHISPER_MODEL", "base")
        if _whisper_model is not None and _whisper_model_name == model_name:
            return _whisper_model

        try:
            import whisper  # type: ignore
        except Exception as e:
            raise SttError(f"Whisper not installed: {e}")

        device = _pick_whisper_device()
        if device:
            _whisper_model = whisper.load_model(model_name, device=device)
        else:
            _whisper_model = whisper.load_model(model_name)
        _whisper_model_name = model_name
        return _whisper_model


def transcribe_file(path: Path) -> SttResult:
    """
    Local Whisper transcription using `openai-whisper`.
    Requires `ffmpeg` installed if input is not raw PCM WAV.
    """
    try:
        if shutil.which("ffmpeg") is None:
            raise SttError(
                "ffmpeg is required for transcription but was not found on PATH. "
                "Install it with `brew install ffmpeg`, then restart the backend."
            )
        if not path.exists():
            raise SttError(f"Audio file not found: {path}")
        if path.stat().st_size < 8_000:
            # Typical WebM/Opus speech clips are much larger; this is usually a tap/click
            # or immediate release that captures near-silence.
            raise SttError(
                "Audio clip is too short to transcribe (file is very small). "
                "Hold record a bit longer and speak clearly, then release to send."
            )
        model = get_whisper_model()
        out = model.transcribe(str(path))
        text = (out.get("text") or "").strip()
        lang = out.get("language")
        if not text:
            raise SttError(
                "Empty transcription. This usually means the audio was silence/too quiet, "
                "or the clip was too short. Try speaking louder and recording 2–3 seconds."
            )
        return SttResult(text=text, language=lang)
    except Exception as e:
        msg = str(e)
        if _is_mps_sparse_failure(msg):
            global _whisper_mps_broken
            _whisper_mps_broken = True
            _clear_whisper_model()
            try:
                model = get_whisper_model()
                out = model.transcribe(str(path))
                text = (out.get("text") or "").strip()
                lang = out.get("language")
                if not text:
                    raise SttError(
                        "Empty transcription. This usually means the audio was silence/too quiet, "
                        "or the clip was too short. Try speaking louder and recording 2–3 seconds."
                    )
                return SttResult(text=text, language=lang)
            except Exception as e2:
                raise SttError(f"Transcription failed: {e2}") from e2
        raise SttError(f"Transcription failed: {e}")

