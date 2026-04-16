from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from .llm import chat_completion
from .rocky_prompt import get_rocky_life_text, get_rocky_speech_style_text
from .storage import SessionPaths, append_log, ensure_session_dirs, get_session_paths
from . import get_timing_logger
from .tts import synthesize_wav_bytes
from .voices import voice_by_id

_timing = get_timing_logger()


@dataclass(frozen=True)
class TurnResult:
    user_text: str
    rocky_text: str
    user_audio_path: Path | None
    rocky_audio_path: Path
    rocky_wav_bytes: bytes


def prior_messages_from_log(sp: SessionPaths) -> list[dict]:
    """OpenAI-style messages from jsonl (user + rocky text only), in order."""
    prior: list[dict] = []
    if not sp.log_file.exists():
        return prior
    for line in sp.log_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if evt.get("type") == "user" and evt.get("text"):
            prior.append({"role": "user", "content": evt["text"]})
        if evt.get("type") == "rocky" and evt.get("text"):
            prior.append({"role": "assistant", "content": evt["text"]})
    return prior


def _system_prompt() -> str:
    # "Rocky" alone strongly biases models toward Rocky Balboa; state canon up front.
    blocks: list[str] = [
        (
            'You are Rocky, the Eridian alien from Andy Weir\'s novel "Project Hail Mary". '
            "You are not Rocky Balboa, not a human boxer, and not any Earth athlete or fighter. "
            "Never claim to be human, a boxer, or to fight in a ring; you are an Eridian."
        ),
        "You are having a spoken conversation with the user.",
        "Keep replies concise (1–4 sentences). Ask clarifying questions when needed.",
        "Do not mention system messages or internal policies.",
    ]
    life = get_rocky_life_text()
    if life:
        blocks.append("## Backstory and personality\n" + life)
    speech = get_rocky_speech_style_text()
    if speech:
        blocks.append("## How Rocky writes and speaks (dialogue)\n" + speech)
    return "\n\n".join(blocks)


async def rocky_reply_turn(*, session_id: str, turn_index: int) -> TurnResult:
    """
    LLM + Rocky TTS after the user line for this turn is already in the jsonl log.
    Builds chat messages as system + full prior from log (including current user).
    """
    _timing.info(
        "timing event=rocky_reply_turn_begin session_id=%s turn=%d",
        session_id,
        turn_index,
    )
    t0 = perf_counter()
    sp: SessionPaths = get_session_paths(session_id)
    ensure_session_dirs(sp)
    prior = prior_messages_from_log(sp)
    if not prior or prior[-1].get("role") != "user":
        raise ValueError("No user message in log for Rocky to reply to")
    user_text = str(prior[-1].get("content", "")).strip()
    if not user_text:
        raise ValueError("User message in log is empty")
    setup_ms = (perf_counter() - t0) * 1000.0

    t_build = perf_counter()
    system_prompt = _system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(prior)
    build_prompt_ms = (perf_counter() - t_build) * 1000.0

    t_llm = perf_counter()
    rocky_text = (await chat_completion(messages)).strip()
    llm_ms = (perf_counter() - t_llm) * 1000.0
    if not rocky_text:
        rocky_text = "I didn't catch that. Can you say it again?"

    append_log(
        sp,
        {
            "type": "rocky",
            "turn": turn_index,
            "text": rocky_text,
        },
    )

    rocky_voice = voice_by_id("rocky")
    if not rocky_voice.ref_audio or not rocky_voice.ref_text:
        raise RuntimeError("Rocky voice is not configured (missing ref_audio/ref_text)")

    t_tts = perf_counter()
    wav = synthesize_wav_bytes(
        text=rocky_text,
        instruct=rocky_voice.instruct,
        ref_audio=str(rocky_voice.ref_audio),
        ref_text=rocky_voice.ref_text,
    )
    t_after_tts = perf_counter()
    tts_ms = (t_after_tts - t_tts) * 1000.0

    rocky_audio_path = sp.rocky_dir / f"rocky_turn_{turn_index:04d}.wav"
    rocky_audio_path.write_bytes(wav.wav_bytes)

    append_log(
        sp,
        {
            "type": "recording",
            "turn": turn_index,
            "rocky_audio": str(rocky_audio_path),
            "sample_rate": wav.sample_rate,
            "bytes": len(wav.wav_bytes),
            "ts": time.time(),
        },
    )

    last_user_audio: Path | None = None
    if sp.log_file.exists():
        for line in sp.log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if evt.get("type") == "user" and evt.get("turn") == turn_index and evt.get("user_audio"):
                last_user_audio = Path(evt["user_audio"])

    t_end = perf_counter()
    post_tts_ms = (t_end - t_after_tts) * 1000.0
    total_ms = (t_end - t0) * 1000.0
    _timing.info(
        "timing event=rocky_reply_turn session_id=%s turn=%d setup_ms=%.1f build_prompt_ms=%.1f "
        "llm_ms=%.1f tts_ms=%.1f post_tts_ms=%.1f total_ms=%.1f prior_msgs=%d system_chars=%d "
        "user_chars=%d rocky_chars=%d",
        session_id,
        turn_index,
        setup_ms,
        build_prompt_ms,
        llm_ms,
        tts_ms,
        post_tts_ms,
        total_ms,
        len(prior),
        len(system_prompt),
        len(user_text),
        len(rocky_text),
    )

    return TurnResult(
        user_text=user_text,
        rocky_text=rocky_text,
        user_audio_path=last_user_audio if last_user_audio and last_user_audio.exists() else None,
        rocky_audio_path=rocky_audio_path,
        rocky_wav_bytes=wav.wav_bytes,
    )

