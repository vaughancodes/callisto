"""Whisper-based audio transcription.

Supports two modes:
  - Local: runs openai-whisper in-process (default)
  - Remote: sends audio to an OpenAI-compatible /v1/audio/transcriptions endpoint
    (e.g. faster-whisper-server, whisper.cpp server, or any compatible API)

Set WHISPER_API_URL to use remote mode. Leave empty for local.
"""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Cache the local model at module level so it's loaded once per process
_model = None


def transcribe_audio(
    audio_path: str | Path,
    model_name: str = "base",
    api_url: str = "",
) -> list[dict]:
    """Transcribe an audio file and return timestamped segments.

    Args:
        audio_path: Path to the audio file (wav, mp3, etc.)
        model_name: Whisper model size ("tiny", "base", "small", "medium", "large")
        api_url: If set, use a remote whisper server instead of local inference.

    Returns:
        List of segment dicts:
            [{"text": "...", "start_ms": 0, "end_ms": 2500, "confidence": -0.3, "chunk_index": 0}, ...]
    """
    if not api_url:
        from callisto.config import Config
        api_url = Config.WHISPER_API_URL

    if api_url:
        return _transcribe_remote(audio_path, model_name, api_url)
    return _transcribe_local(audio_path, model_name)


def _transcribe_local(audio_path: str | Path, model_name: str) -> list[dict]:
    """Run whisper in-process."""
    import whisper as whisper_lib

    global _model
    if _model is None:
        logger.info("Loading Whisper model '%s'...", model_name)
        _model = whisper_lib.load_model(model_name)
        logger.info("Whisper model loaded.")

    audio_path = str(audio_path)
    logger.info("Transcribing %s locally with model '%s'...", audio_path, model_name)
    result = _model.transcribe(audio_path, language="en", verbose=False)

    segments = []
    for i, seg in enumerate(result.get("segments", [])):
        segments.append({
            "text": seg["text"].strip(),
            "start_ms": int(seg["start"] * 1000),
            "end_ms": int(seg["end"] * 1000),
            "confidence": seg.get("avg_logprob", 0.0),
            "chunk_index": i,
        })

    logger.info("Transcription complete: %d segments from %s", len(segments), audio_path)
    return segments


def _transcribe_remote(audio_path: str | Path, model_name: str, api_url: str) -> list[dict]:
    """Send audio to a remote OpenAI-compatible whisper server.

    Expects the server to implement POST /v1/audio/transcriptions
    with response_format=verbose_json (returns segments with timestamps).
    """
    audio_path = Path(audio_path)
    url = api_url.rstrip("/") + "/v1/audio/transcriptions"

    logger.info("Transcribing %s via remote server %s...", audio_path, api_url)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            url,
            files={"file": (audio_path.name, f, "audio/wav")},
            data={
                "model": model_name,
                "response_format": "verbose_json",
                "language": "en",
            },
            timeout=120,
        )

    resp.raise_for_status()
    data = resp.json()

    segments = []
    for i, seg in enumerate(data.get("segments", [])):
        segments.append({
            "text": seg.get("text", "").strip(),
            "start_ms": int(float(seg.get("start", 0)) * 1000),
            "end_ms": int(float(seg.get("end", 0)) * 1000),
            "confidence": seg.get("avg_logprob", 0.0),
            "chunk_index": i,
        })

    logger.info("Remote transcription complete: %d segments from %s", len(segments), audio_path)
    return segments
