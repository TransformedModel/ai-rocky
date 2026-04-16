from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Optional

import numpy as np
import soundfile as sf

from . import get_timing_logger

_timing = get_timing_logger()


_model_lock = threading.Lock()
_generate_lock = threading.Lock()
_model = None


@dataclass(frozen=True)
class TtsResult:
    wav_bytes: bytes
    sample_rate: int


def _pick_device() -> str:
    forced = os.getenv("OMNIVOICE_DEVICE")
    if forced:
        return forced

    try:
        import torch  # type: ignore

        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


def _pick_dtype(device: str):
    try:
        import torch  # type: ignore

        if device.startswith("cuda") or device == "mps":
            return torch.float16
        return torch.float32
    except Exception:
        return None


def get_model():
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        from omnivoice import OmniVoice  # type: ignore

        device = _pick_device()
        dtype = _pick_dtype(device)

        kwargs = {"device_map": device}
        if dtype is not None:
            kwargs["dtype"] = dtype

        t0 = perf_counter()
        _model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", **kwargs)
        load_ms = (perf_counter() - t0) * 1000.0
        _timing.info(
            "timing event=omnivoice_model_load elapsed_ms=%.1f device=%s dtype=%s",
            load_ms,
            device,
            str(dtype) if dtype is not None else "default",
        )
        return _model


def synthesize_wav_bytes(
    *,
    text: str,
    instruct: Optional[str] = None,
    ref_audio: Optional[str] = None,
    ref_text: Optional[str] = None,
) -> TtsResult:
    ref_label = Path(ref_audio).name if ref_audio else "none"
    _timing.info(
        "timing event=omnivoice_synthesize_begin text_chars=%d ref_audio=%s",
        len(text),
        ref_label,
    )
    t0 = perf_counter()
    model = get_model()
    get_model_ms = (perf_counter() - t0) * 1000.0

    t1 = perf_counter()
    with _generate_lock:
        audio_list = model.generate(
            text=text,
            instruct=instruct,
            ref_audio=ref_audio,
            ref_text=ref_text,
        )
    generate_ms = (perf_counter() - t1) * 1000.0

    if not audio_list:
        raise RuntimeError("OmniVoice returned no audio")

    audio0 = np.asarray(audio_list[0], dtype=np.float32)
    sample_rate = 24000

    t2 = perf_counter()
    buf = io.BytesIO()
    sf.write(buf, audio0, sample_rate, format="WAV")
    wav_bytes = buf.getvalue()
    encode_ms = (perf_counter() - t2) * 1000.0

    _timing.info(
        "timing event=omnivoice_synthesize_end get_model_ms=%.1f generate_ms=%.1f wav_encode_ms=%.1f "
        "text_chars=%d ref_audio=%s wav_bytes=%d",
        get_model_ms,
        generate_ms,
        encode_ms,
        len(text),
        ref_label,
        len(wav_bytes),
    )
    return TtsResult(wav_bytes=wav_bytes, sample_rate=sample_rate)

