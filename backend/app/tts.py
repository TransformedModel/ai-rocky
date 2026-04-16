from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np
import soundfile as sf


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

        _model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", **kwargs)
        return _model


def synthesize_wav_bytes(
    *,
    text: str,
    instruct: Optional[str] = None,
    ref_audio: Optional[str] = None,
    ref_text: Optional[str] = None,
) -> TtsResult:
    model = get_model()

    with _generate_lock:
        audio_list = model.generate(
            text=text,
            instruct=instruct,
            ref_audio=ref_audio,
            ref_text=ref_text,
        )

    if not audio_list:
        raise RuntimeError("OmniVoice returned no audio")

    audio0 = np.asarray(audio_list[0], dtype=np.float32)
    sample_rate = 24000

    buf = io.BytesIO()
    sf.write(buf, audio0, sample_rate, format="WAV")
    return TtsResult(wav_bytes=buf.getvalue(), sample_rate=sample_rate)

