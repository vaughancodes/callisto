"""Twilio Media Streams WebSocket server.

Standalone async process that accepts incoming WebSocket connections from
Twilio, decodes the audio stream, and:
  - Transcribes via Deepgram streaming OR batched Whisper (configurable)
  - Publishes transcript chunks to Redis Streams for real-time evaluation
  - Persists transcript chunks to Postgres
  - Saves accumulated audio as WAV on call end for cold-path analysis

STT provider selection (STT_PROVIDER env var):
  - "auto" (default): uses Deepgram if DEEPGRAM_API_KEY is set, otherwise Whisper
  - "deepgram": Deepgram streaming (requires DEEPGRAM_API_KEY)
  - "whisper": batched Whisper segments (local or remote via WHISPER_API_URL)

Run directly:
    python -m callisto.ingestion.server
"""

import asyncio
import json
import logging
import math
import os
import tempfile
import wave
from datetime import datetime
from pathlib import Path

import redis as sync_redis
import websockets

from callisto.ingestion.audio import AudioBuffer, decode_twilio_media

logger = logging.getLogger(__name__)

LISTEN_HOST = os.environ.get("INGESTION_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("INGESTION_PORT", "5310"))
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/tmp/callisto_recordings")


def _get_redis():
    from callisto.config import Config
    redis_url = os.environ.get("REDIS_URL", Config.REDIS_URL)
    return sync_redis.from_url(redis_url, decode_responses=True)


def _get_stt_provider() -> str:
    """Determine which STT provider to use."""
    from callisto.config import Config
    provider = Config.STT_PROVIDER.lower()
    if provider == "auto":
        return "deepgram" if Config.DEEPGRAM_API_KEY else "whisper"
    return provider


class CallSession:
    """State for a single active Twilio Media Stream connection."""

    def __init__(self):
        self.call_sid: str | None = None
        self.stream_sid: str | None = None
        self.tenant_id: str | None = None
        self.custom_params: dict = {}
        self.buffer = AudioBuffer(chunk_duration_ms=500)
        self.chunk_index = 0
        self.all_pcm = bytearray()
        self.started_at: datetime | None = None
        self.transcript_chunk_index = 0
        self.deepgram = None
        self.redis_client = None
        self.stt_provider: str = "whisper"

        # Whisper batching state
        self.transcription_buffer = bytearray()
        self.transcription_offset_ms = 0


async def handle_twilio_stream(websocket):
    """Handle a single Twilio Media Stream WebSocket connection."""
    session = CallSession()
    session.stt_provider = _get_stt_provider()
    logger.info("New WebSocket connection from %s", websocket.remote_address)

    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            event = message.get("event")

            if event == "connected":
                logger.info("Twilio stream connected (protocol=%s)", message.get("protocol"))

            elif event == "start":
                start = message.get("start", {})
                session.call_sid = start.get("callSid")
                session.stream_sid = start.get("streamSid")
                session.custom_params = start.get("customParameters", {})
                session.tenant_id = session.custom_params.get("tenant_id")
                session.started_at = datetime.now()

                logger.info(
                    "Stream started: call_sid=%s stt=%s tenant_id=%s",
                    session.call_sid, session.stt_provider, session.tenant_id,
                )

                _create_call_record(session)

                # Set up Redis and announce the stream
                session.redis_client = _get_redis()
                stream_key = f"call:{session.call_sid}:chunks"
                session.redis_client.publish("callisto:active_streams", stream_key)

                # Start Deepgram if that's the provider
                if session.stt_provider == "deepgram":
                    await _start_deepgram(session)

            elif event == "media":
                media = message.get("media", {})
                payload = media.get("payload")
                if not payload:
                    continue

                pcm_16khz = decode_twilio_media(payload)
                session.all_pcm.extend(pcm_16khz)

                chunks = session.buffer.ingest(pcm_16khz)
                for chunk in chunks:
                    session.chunk_index += 1

                if session.stt_provider == "deepgram" and session.deepgram:
                    await session.deepgram.send_audio(pcm_16khz)
                elif session.stt_provider == "whisper":
                    session.transcription_buffer.extend(pcm_16khz)
                    from callisto.config import Config
                    segment_bytes = 16000 * 2 * Config.WHISPER_SEGMENT_SECONDS
                    if len(session.transcription_buffer) >= segment_bytes:
                        _whisper_transcribe_and_publish(session)

            elif event == "stop":
                logger.info(
                    "Stream stopped: call_sid=%s (%d chunks, %d bytes PCM)",
                    session.call_sid, session.chunk_index, len(session.all_pcm),
                )

                if session.buffer.has_remaining():
                    remaining = session.buffer.flush()
                    session.all_pcm.extend(remaining)
                    session.chunk_index += 1

                # Flush STT
                if session.stt_provider == "deepgram" and session.deepgram:
                    await session.deepgram.close()
                elif session.stt_provider == "whisper" and len(session.transcription_buffer) > 0:
                    _whisper_transcribe_and_publish(session)

                # End-of-stream marker
                if session.redis_client and session.call_sid:
                    stream_key = f"call:{session.call_sid}:chunks"
                    session.redis_client.xadd(stream_key, {
                        "call_id": session.call_sid,
                        "tenant_id": session.tenant_id or "",
                        "text": "",
                        "start_ms": "0",
                        "end_ms": "0",
                        "chunk_index": str(session.transcript_chunk_index),
                        "type": "end",
                    })

                if session.call_sid and len(session.all_pcm) > 0:
                    _on_call_end(session)

    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket closed: call_sid=%s", session.call_sid)
        if session.deepgram:
            await session.deepgram.close()
        if session.call_sid and len(session.all_pcm) > 0:
            _on_call_end(session)


# ---------------------------------------------------------------------------
# Deepgram streaming
# ---------------------------------------------------------------------------

async def _start_deepgram(session: CallSession):
    """Initialize Deepgram streaming for this call session."""
    from callisto.config import Config
    from callisto.transcription.deepgram import DeepgramStreamer

    api_key = Config.DEEPGRAM_API_KEY
    if not api_key:
        logger.warning("DEEPGRAM_API_KEY not set — falling back to whisper")
        session.stt_provider = "whisper"
        return

    async def on_transcript(*, text, start_ms, end_ms, is_final, confidence):
        if not text.strip() or not is_final:
            return
        _publish_chunk(session, text, start_ms, end_ms, confidence)

    session.deepgram = DeepgramStreamer(
        api_key=api_key,
        on_transcript=on_transcript,
        call_id=session.call_sid or "",
    )
    try:
        await session.deepgram.connect()
    except Exception:
        logger.exception("Failed to connect to Deepgram — falling back to whisper")
        session.deepgram = None
        session.stt_provider = "whisper"


# ---------------------------------------------------------------------------
# Whisper batched segments
# ---------------------------------------------------------------------------

def _whisper_transcribe_and_publish(session: CallSession):
    """Run Whisper on the accumulated audio segment and publish results."""
    from callisto.config import Config
    from callisto.transcription.whisper import transcribe_audio

    pcm_data = bytes(session.transcription_buffer)
    session.transcription_buffer = bytearray()

    duration_ms = len(pcm_data) // (16000 * 2) * 1000
    start_ms = session.transcription_offset_ms
    session.transcription_offset_ms = start_ms + duration_ms

    # Write temp WAV for Whisper
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_data)

        model = os.environ.get("WHISPER_MODEL", Config.WHISPER_MODEL)
        segments = transcribe_audio(tmp.name, model_name=model)
    except Exception:
        logger.exception("Whisper transcription failed for %s", session.call_sid)
        return
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    for seg in segments:
        adjusted_start = start_ms + seg["start_ms"]
        adjusted_end = start_ms + seg["end_ms"]
        confidence = max(0.0, min(1.0, math.exp(seg.get("confidence", -0.5))))
        _publish_chunk(session, seg["text"], adjusted_start, adjusted_end, confidence)


# ---------------------------------------------------------------------------
# Shared: publish transcript chunk to Redis + Postgres
# ---------------------------------------------------------------------------

def _publish_chunk(session: CallSession, text: str, start_ms: int, end_ms: int, confidence: float):
    """Publish a transcript chunk to Redis Streams and persist to Postgres."""
    chunk_idx = session.transcript_chunk_index
    session.transcript_chunk_index += 1

    logger.info("Chunk %d: [%d-%dms] %s", chunk_idx, start_ms, end_ms, text[:60])

    if session.redis_client and session.call_sid:
        stream_key = f"call:{session.call_sid}:chunks"
        session.redis_client.xadd(stream_key, {
            "call_id": session.call_sid,
            "tenant_id": session.tenant_id or "",
            "text": text,
            "start_ms": str(start_ms),
            "end_ms": str(end_ms),
            "chunk_index": str(chunk_idx),
            "speaker": "unknown",
            "confidence": str(confidence),
            "type": "transcript",
        })

    _persist_transcript_chunk(session, text, start_ms, end_ms, chunk_idx, confidence)


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------

def _persist_transcript_chunk(session, text, start_ms, end_ms, chunk_idx, confidence):
    from callisto.app import create_app
    from callisto.extensions import db
    from callisto.models import Call, Transcript

    app = create_app()
    with app.app_context():
        call = Call.query.filter_by(external_id=session.call_sid).first()
        if not call:
            return

        chunk = Transcript(
            call_id=call.id,
            tenant_id=call.tenant_id,
            speaker="unknown",
            text=text,
            start_ms=start_ms,
            end_ms=end_ms,
            confidence=max(0.0, min(1.0, confidence)),
            chunk_index=chunk_idx,
        )
        db.session.add(chunk)
        db.session.commit()


def _create_call_record(session: CallSession):
    from callisto.app import create_app
    from callisto.extensions import db
    from callisto.models import Call

    app = create_app()
    with app.app_context():
        existing = Call.query.filter_by(external_id=session.call_sid).first()
        if existing:
            logger.info("Call record already exists for %s", session.call_sid)
            return

        # Look up contact by caller phone number
        contact_id = None
        caller = session.custom_params.get("from", "")
        logger.info("Contact lookup: tenant=%s caller='%s'", session.tenant_id, caller)
        if session.tenant_id and caller:
            from callisto.api.contacts import lookup_contact_by_phone
            contact = lookup_contact_by_phone(session.tenant_id, caller)
            if contact:
                contact_id = contact.id
                logger.info("Matched caller %s to contact %s", caller, contact.name)
            else:
                logger.info("No contact match for %s", caller)

        call = Call(
            tenant_id=session.tenant_id,
            external_id=session.call_sid,
            stream_sid=session.stream_sid,
            contact_id=contact_id,
            source="twilio",
            direction=session.custom_params.get("direction", "inbound"),
            caller_number=session.custom_params.get("from", "unknown"),
            callee_number=session.custom_params.get("to", "unknown"),
            status="active",
            started_at=session.started_at or datetime.now(),
            consent_given=True,
            metadata_={
                "stream_sid": session.stream_sid,
                "custom_params": session.custom_params,
            },
        )
        db.session.add(call)
        db.session.commit()
        logger.info("Created call record %s for call_sid=%s", call.id, session.call_sid)


def _on_call_end(session: CallSession):
    from callisto.app import create_app
    from callisto.extensions import db
    from callisto.models import Call

    dest_dir = os.path.join(RECORDINGS_DIR, session.tenant_id or "unknown")
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    wav_path = os.path.join(dest_dir, f"{session.call_sid}.wav")

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(bytes(session.all_pcm))

    duration_sec = len(session.all_pcm) // (16000 * 2)
    logger.info("Saved %ds of audio to %s", duration_sec, wav_path)

    app = create_app()
    with app.app_context():
        call = Call.query.filter_by(external_id=session.call_sid).first()
        if not call:
            logger.error("No call record found for call_sid=%s", session.call_sid)
            return

        call.status = "processing"
        call.ended_at = datetime.now()
        call.duration_sec = duration_sec
        db.session.commit()

        from callisto.tasks import process_call_end
        process_call_end.delay(str(call.id), str(call.tenant_id), wav_path)
        logger.info("Dispatched cold-path pipeline for call %s", call.id)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    provider = _get_stt_provider()
    logger.info(
        "Starting Twilio Media Stream server on %s:%d (stt=%s)",
        LISTEN_HOST, LISTEN_PORT, provider,
    )

    async with websockets.serve(
        handle_twilio_stream,
        LISTEN_HOST,
        LISTEN_PORT,
        max_size=2**20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
