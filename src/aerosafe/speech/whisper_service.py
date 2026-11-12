"""Local speech-to-text with Whisper (via faster-whisper).

Audio stays on the machine. The model is loaded lazily so the rest of the
project (and the tests) work without the optional `speech` extra installed.
"""
from dataclasses import dataclass
from functools import lru_cache

from aerosafe.config import get_settings

# A short prompt of domain words nudges Whisper toward aviation vocabulary.
AVIATION_PROMPT = (
    "Airbus A320, landing gear, nose gear, main gear, retraction actuator, "
    "hydraulic pressure, ATA chapter, airworthiness directive, hangar, borescope, "
    "train d'atterrissage, perte de pression hydraulique, vérin."
)


@dataclass
class Transcript:
    text: str
    language: str
    language_probability: float
    duration: float


@lru_cache(maxsize=1)
def _load_model(size: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel  # imported lazily on purpose

    return WhisperModel(size, device=device, compute_type=compute_type)


def transcribe(audio_path: str, language: str | None = None) -> Transcript:
    """Transcribe an audio file. Leave `language` empty to auto-detect FR/EN."""
    cfg = get_settings()
    model = _load_model(cfg.whisper_model, cfg.whisper_device, cfg.whisper_compute_type)
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        language=language,
        vad_filter=True,
        initial_prompt=AVIATION_PROMPT,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return Transcript(text, info.language, float(info.language_probability), float(info.duration))
