from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from time import perf_counter
from typing import Literal, Optional

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

# Ensure env vars from `backend/.env` are available even when uvicorn doesn't load them.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

from .conversation import rocky_reply_turn
from .storage import append_log, delete_session_recordings, ensure_session_dirs, get_session_paths, new_session
from . import get_timing_logger
from .tts import synthesize_wav_bytes
from .voices import Voice, get_voices, voice_by_id

logger = logging.getLogger(__name__)
_timing = get_timing_logger()

app = FastAPI(title="OmniVoice Chat MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VoiceOut(BaseModel):
    id: str
    label: str
    mode: Literal["design", "clone"]
    instruct: Optional[str] = None
    ref_audio_name: Optional[str] = None


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voiceId: str = Field(min_length=1, max_length=128)


def _voice_to_out(v: Voice) -> VoiceOut:
    return VoiceOut(
        id=v.id,
        label=v.label,
        mode=v.mode,
        instruct=v.instruct if v.mode == "design" else None,
        ref_audio_name=v.ref_audio.name if v.ref_audio else None,
    )


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/voices", response_model=list[VoiceOut])
def list_voices():
    return [_voice_to_out(v) for v in get_voices()]


@app.post("/api/tts")
def tts(body: TtsIn):
    try:
        voice = voice_by_id(body.voiceId)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    t0 = perf_counter()
    try:
        if voice.mode == "design":
            result = synthesize_wav_bytes(text=body.text, instruct=voice.instruct)
        else:
            if not voice.ref_audio or not voice.ref_text:
                raise HTTPException(status_code=500, detail="Clone voice misconfigured")
            if not voice.ref_audio.exists():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Missing reference audio for voiceId={voice.id}. "
                        f"Expected file at {voice.ref_audio}."
                    ),
                )
            result = synthesize_wav_bytes(
                text=body.text,
                ref_audio=str(voice.ref_audio),
                ref_text=voice.ref_text,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    finally:
        wall_ms = (perf_counter() - t0) * 1000.0
        _timing.info(
            "timing event=http_tts voice_id=%s mode=%s wall_ms=%.1f text_chars=%d",
            body.voiceId,
            voice.mode,
            wall_ms,
            len(body.text),
        )

    return Response(content=result.wav_bytes, media_type="audio/wav")


class ConversationStartOut(BaseModel):
    sessionId: str


class ConversationEndIn(BaseModel):
    sessionId: str


class ConversationTurnOut(BaseModel):
    sessionId: str
    turn: int
    userText: str
    rockyText: str
    rockyAudioUrl: str


@app.post("/api/conversation/start", response_model=ConversationStartOut)
def conversation_start():
    sp = new_session()
    ensure_session_dirs(sp)
    append_log(sp, {"type": "session_start", "session": sp.session_id})
    return ConversationStartOut(sessionId=sp.session_id)


@app.post("/api/conversation/reply-turn", response_model=ConversationTurnOut)
async def conversation_reply_turn(
    sessionId: str = Form(...),
    turn: int = Form(...),
    typedText: Optional[str] = Form(None),
):
    """Append typed user line if provided, then LLM + Rocky TTS. For audio turns, user line is already in log."""
    sp = get_session_paths(sessionId)
    ensure_session_dirs(sp)

    if typedText is not None and typedText.strip():
        append_log(
            sp,
            {
                "type": "user",
                "turn": turn,
                "text": typedText.strip(),
                "user_audio": None,
            },
        )

    try:
        result = await rocky_reply_turn(session_id=sessionId, turn_index=turn)
    except HTTPException:
        raise
    except Exception as e:
        append_log(sp, {"type": "turn_error", "turn": turn, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

    rocky_audio_url = f"/api/conversation/{sessionId}/recordings/{result.rocky_audio_path.name}"
    return ConversationTurnOut(
        sessionId=sessionId,
        turn=turn,
        userText=result.user_text,
        rockyText=result.rocky_text,
        rockyAudioUrl=rocky_audio_url,
    )


@app.get("/api/conversation/{sessionId}/recordings/{filename}")
def conversation_recording(sessionId: str, filename: str):
    sp = get_session_paths(sessionId)
    path = sp.rocky_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")
    return Response(content=path.read_bytes(), media_type="audio/wav")


@app.post("/api/conversation/end")
def conversation_end(body: ConversationEndIn):
    sp = get_session_paths(body.sessionId)
    append_log(sp, {"type": "session_end", "session": body.sessionId})
    delete_session_recordings(sp)
    return {"ok": True}


_frontend_dist = os.getenv("FRONTEND_DIST", "").strip()
if _frontend_dist:
    _fd = Path(_frontend_dist)
    if _fd.is_dir():
        from starlette.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(_fd), html=True), name="frontend")


def _on_railway() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))


@app.on_event("startup")
def _warm_start():
    """Preload OmniVoice in a daemon thread so HTTP comes up fast.

    On Railway, background warm start often OOMs small instances (torch + weights).
    Skip unless ``OMNIVOICE_WARM_START`` is set to a truthy value (``1`` / ``true`` / ``yes``).
    """
    if _on_railway() and os.getenv("OMNIVOICE_WARM_START", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        logger.warning(
            "Skipping OmniVoice warm start on Railway (avoids OOM during boot). "
            "Set OMNIVOICE_WARM_START=1 only if the service has enough RAM (often 8 GB+). "
            "First TTS/reply-turn will load weights and may take several minutes."
        )
        return

    def _load():
        try:
            from .tts import get_model

            get_model()
        except Exception:
            pass

    threading.Thread(target=_load, daemon=True).start()

