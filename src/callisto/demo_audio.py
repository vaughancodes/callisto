"""TTS rendering for demo call transcripts.

Each demo call has a scripted transcript with timestamped chunks split
between an ``internal`` and ``external`` speaker. We render each chunk
through Microsoft Edge's neural TTS (via the open-source ``edge-tts``
client; no API key required) using a different voice per speaker, then
splice the chunks back into a single WAV with silence between turns so
the audio's timing matches the transcript's ``start_ms`` values.

Voicemails get a single voice (the caller).

Generation runs once at API boot in a background thread and writes a
hash file so subsequent boots skip work unless the fixtures changed.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import wave
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


VOICE_INTERNAL = "en-US-AndrewNeural"   # Callisto user
VOICE_EXTERNAL = "en-US-AriaNeural"     # Other party / caller

# Fallback voice when speaker is "unknown" or anything else.
VOICE_DEFAULT = VOICE_EXTERNAL

OUTPUT_SAMPLE_RATE = 16000  # match the real ingestion server's WAVs
OUTPUT_SAMPLE_WIDTH = 2     # 16-bit PCM

# Cap silence between chunks. The fixture transcripts use sparse start_ms
# values to space dialogue out for readability; rendering audio with that
# exact spacing produces unnaturally long silent gaps. We honor the gap
# the fixture asked for, but never more than this many milliseconds.
MAX_INTER_CHUNK_SILENCE_MS = 500


def _audio_dir() -> Path:
    base = os.environ.get("DEMO_AUDIO_DIR", "data/demo_audio")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    (p / "voicemail").mkdir(parents=True, exist_ok=True)
    return p


def call_audio_path(call_id: str) -> Path:
    return _audio_dir() / f"{call_id}.wav"


def call_transcript_path(call_id: str) -> Path:
    return _audio_dir() / f"{call_id}.transcript.json"


def voicemail_audio_path(call_id: str) -> Path:
    return _audio_dir() / "voicemail" / f"{call_id}.wav"


def voicemail_transcript_path(call_id: str) -> Path:
    return _audio_dir() / "voicemail" / f"{call_id}.transcript.json"


def _voice_for(speaker: str) -> str:
    if speaker == "internal":
        return VOICE_INTERNAL
    if speaker == "external":
        return VOICE_EXTERNAL
    return VOICE_DEFAULT


async def _tts_to_pcm(text: str, voice: str) -> bytes:
    """Render text → MP3 via edge-tts, decode → mono 16kHz 16-bit PCM."""
    import edge_tts
    from pydub import AudioSegment

    communicate = edge_tts.Communicate(text=text, voice=voice)
    mp3_buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            mp3_buf.write(chunk["data"])

    mp3_buf.seek(0)
    seg = AudioSegment.from_file(mp3_buf, format="mp3")
    seg = seg.set_channels(1).set_frame_rate(OUTPUT_SAMPLE_RATE).set_sample_width(
        OUTPUT_SAMPLE_WIDTH
    )
    return seg.raw_data


def _silence_pcm(duration_ms: int) -> bytes:
    n_frames = max(0, int(OUTPUT_SAMPLE_RATE * duration_ms / 1000))
    return b"\x00" * (n_frames * OUTPUT_SAMPLE_WIDTH)


async def _render_transcript(
    chunks: Iterable[dict],
    *,
    base_offset_ms: int = 0,
) -> tuple[bytes, list[dict]]:
    """Render an ordered iterable of transcript chunks into one mono PCM
    blob. Returns (pcm, rebased_chunks) where rebased_chunks have their
    start_ms / end_ms updated to reflect the actual audio positions
    (with inter-chunk silence capped at MAX_INTER_CHUNK_SILENCE_MS).
    The caller writes the rebased chunks alongside the WAV so the
    frontend transcript display stays in sync with the tightened audio.
    """
    pcm = bytearray()
    cursor_ms = 0
    rebased: list[dict] = []
    for i, chunk in enumerate(chunks):
        scheduled_ms = max(0, int(chunk.get("start_ms", 0)) - base_offset_ms)
        # Honor the requested gap, but cap to keep playback natural.
        gap_target = max(0, scheduled_ms - cursor_ms)
        gap = min(gap_target, MAX_INTER_CHUNK_SILENCE_MS)
        if gap > 0:
            pcm.extend(_silence_pcm(gap))
            cursor_ms += gap

        text = (chunk.get("text") or "").strip()
        speaker = chunk.get("speaker") or "external"
        actual_start_ms = cursor_ms

        if not text:
            continue
        voice = _voice_for(speaker)
        try:
            seg_pcm = await _tts_to_pcm(text, voice)
        except Exception as exc:
            logger.warning(
                "TTS failed for chunk (voice=%s): %s; substituting silence.",
                voice, exc,
            )
            seg_pcm = _silence_pcm(max(2000, len(text) * 60))
        pcm.extend(seg_pcm)
        seg_ms = (len(seg_pcm) // OUTPUT_SAMPLE_WIDTH) * 1000 // OUTPUT_SAMPLE_RATE
        cursor_ms += seg_ms

        rebased.append({
            "speaker": speaker,
            "text": text,
            "start_ms": actual_start_ms + base_offset_ms,
            "end_ms": cursor_ms + base_offset_ms,
            "confidence": float(chunk.get("confidence", 0.92)),
            "chunk_index": i,
        })
    return bytes(pcm), rebased


def _write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(OUTPUT_SAMPLE_WIDTH)
        wf.setframerate(OUTPUT_SAMPLE_RATE)
        wf.writeframes(pcm)


def _fixture_signature() -> str:
    """Hash all transcript text + timing so we can detect when fixtures
    change and need re-rendering. Encompasses voice mapping too — bump
    the version constant to force a regen across the board.
    """
    from callisto import demo_fixtures as f

    VERSION = "v1"
    payload = {
        "version": VERSION,
        "voice_internal": VOICE_INTERNAL,
        "voice_external": VOICE_EXTERNAL,
        "transcripts": {
            cid: [
                (c.get("speaker"), c.get("text"), c.get("start_ms"))
                for c in chunks
            ]
            for cid, chunks in f.TRANSCRIPTS.items()
        },
        "voicemails": {
            cid: [
                (c.get("speaker"), c.get("text"), c.get("start_ms"))
                for c in chunks
            ]
            for cid, chunks in f.VOICEMAIL_TRANSCRIPTS.items()
        },
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


async def _generate_async() -> None:
    from callisto import demo_fixtures as f

    # Full call audio (everyone's transcript).
    for cid, chunks in f.TRANSCRIPTS.items():
        target = call_audio_path(cid)
        if target.exists():
            continue
        try:
            pcm, rebased = await _render_transcript(chunks)
            if pcm:
                _write_wav(target, pcm)
                call_transcript_path(cid).write_text(json.dumps(rebased))
                logger.info(
                    "Demo audio rendered: %s (%d chunks, %d bytes)",
                    target, len(rebased), len(pcm),
                )
        except Exception as exc:
            logger.warning("Demo audio generation failed for %s: %s", cid, exc)

    # Voicemail-only audio: external voice only, rebased so the very
    # first chunk lands at 0ms in the audio (no leading silence — the
    # voicemail player's 0:00 is the caller's first word).
    for cid, vm_chunks in f.VOICEMAIL_TRANSCRIPTS.items():
        target = voicemail_audio_path(cid)
        if target.exists() or not vm_chunks:
            continue
        first_ms = int(vm_chunks[0].get("start_ms") or 0)
        try:
            pcm, rebased = await _render_transcript(
                vm_chunks, base_offset_ms=first_ms
            )
            if pcm:
                _write_wav(target, pcm)
                voicemail_transcript_path(cid).write_text(
                    json.dumps({
                        "rebased_started_at_ms": first_ms,
                        "chunks": rebased,
                    })
                )
                logger.info(
                    "Voicemail audio rendered: %s (%d chunks)",
                    target, len(rebased),
                )
        except Exception as exc:
            logger.warning(
                "Voicemail audio generation failed for %s: %s", cid, exc
            )


def _wipe_existing(out: Path) -> None:
    for pattern in ("*.wav", "*.transcript.json"):
        for p in list(out.glob(pattern)):
            try:
                p.unlink()
            except OSError:
                pass
    vm = out / "voicemail"
    if vm.exists():
        for pattern in ("*.wav", "*.transcript.json"):
            for p in list(vm.glob(pattern)):
                try:
                    p.unlink()
                except OSError:
                    pass


def regenerate_demo_audio() -> None:
    """Render every demo call's audio synchronously. Skips calls whose
    files already exist and whose fixture signature is unchanged. Run
    manually with ``python -m callisto.demo_audio`` whenever you edit
    transcripts in ``demo_fixtures.py``; the resulting WAVs are checked
    into the repo and served as static assets, so the API itself never
    runs TTS at boot.
    """
    out = _audio_dir()
    sig_path = out / ".signature"
    current_sig = _fixture_signature()
    prior = sig_path.read_text().strip() if sig_path.exists() else ""
    if prior == current_sig and any(out.iterdir()):
        logger.info("Demo audio up to date (signature %s).", current_sig[:10])
        return
    if prior and prior != current_sig:
        logger.info("Demo fixtures changed; wiping prior audio.")
        _wipe_existing(out)
    asyncio.run(_generate_async())
    sig_path.write_text(current_sig)
    logger.info("Demo audio regeneration complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    regenerate_demo_audio()
