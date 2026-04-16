from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


VoiceMode = Literal["design", "clone"]


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    mode: VoiceMode
    instruct: Optional[str] = None
    ref_audio: Optional[Path] = None
    ref_text: Optional[str] = None


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "voices"


def get_voices() -> list[Voice]:
    voices: list[Voice] = [
        Voice(
            id="female_low_british",
            label="Female, low pitch, British accent",
            mode="design",
            instruct="female, low pitch, british accent",
        ),
        Voice(
            id="male_high_american",
            label="Male, high pitch, American accent",
            mode="design",
            instruct="male, high pitch, american accent",
        ),
        Voice(
            id="whisper_female",
            label="Female, whisper",
            mode="design",
            instruct="female, whisper",
        ),
        Voice(
            id="rocky",
            label="Rocky",
            mode="clone",
            ref_audio=ASSETS_DIR / "Rocky-2.wav",
            ref_text="If you account for the time it took your Beatles to get there and the time it took for light to get from Sol to Erid, I think it took less than one of your years to get it done. ",
        ),
        Voice(
            id="clone_sample_1",
            label="Clone: sample 1 (add your own ref)",
            mode="clone",
            ref_audio=ASSETS_DIR / "sample_1.wav",
            ref_text="(replace this with the transcription of sample_1.wav)",
        ),
    ]
    return voices


def voice_by_id(voice_id: str) -> Voice:
    for v in get_voices():
        if v.id == voice_id:
            return v
    raise KeyError(f"Unknown voiceId: {voice_id}")

