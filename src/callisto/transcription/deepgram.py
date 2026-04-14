"""Deepgram streaming transcription client.

Opens a WebSocket connection to Deepgram's streaming API per active call.
Audio chunks are forwarded in real time, and transcript fragments are
returned via a callback.

Deepgram expects raw PCM audio (16-bit, 16kHz, mono) or mulaw. We send
the already-decoded 16kHz PCM from the ingestion audio pipeline.
"""

import asyncio
import json
import logging
import os

import websockets

logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramStreamer:
    """Manages a streaming WebSocket connection to Deepgram for one call track."""

    def __init__(
        self,
        api_key: str,
        on_transcript,
        call_id: str = "",
        speaker: str = "unknown",
    ):
        """
        Args:
            api_key: Deepgram API key.
            on_transcript: Async callback called with (text, start_ms, end_ms, is_final,
                           confidence, speaker) for each transcript fragment.
            call_id: For logging.
            speaker: Label for the speaker on this track (e.g. "external", "internal").
        """
        self.api_key = api_key
        self.on_transcript = on_transcript
        self.call_id = call_id
        self.speaker = speaker
        self._ws = None
        self._receive_task = None
        self._closed = False

    async def connect(self):
        """Open the streaming WebSocket to Deepgram."""
        params = (
            "?encoding=linear16"
            "&sample_rate=16000"
            "&channels=1"
            "&model=nova-2"
            "&punctuate=true"
            "&interim_results=true"
            "&endpointing=300"
            "&utterance_end_ms=1500"
        )
        url = DEEPGRAM_WS_URL + params
        headers = {"Authorization": f"Token {self.api_key}"}

        try:
            self._ws = await websockets.connect(
                url, additional_headers=headers
            )
        except websockets.exceptions.InvalidStatus as e:
            logger.error(
                "Deepgram rejected connection for %s: HTTP %s body=%s",
                self.call_id,
                e.response.status_code,
                e.response.body[:500] if e.response.body else "(empty)",
            )
            raise

        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("Deepgram stream connected for call %s", self.call_id)

    async def send_audio(self, pcm_bytes: bytes):
        """Send a chunk of 16kHz 16-bit PCM audio to Deepgram."""
        if self._ws and not self._closed:
            try:
                await self._ws.send(pcm_bytes)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Deepgram connection closed while sending for %s", self.call_id)
                self._closed = True

    async def close(self):
        """Signal end of audio and close the connection."""
        if self._ws and not self._closed:
            self._closed = True
            try:
                # Send empty byte message to signal end of audio
                await self._ws.send(b"")
                # Wait briefly for final transcripts
                await asyncio.sleep(1.0)
                await self._ws.close()
            except Exception:
                pass

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        logger.info("Deepgram stream closed for call %s", self.call_id)

    async def _receive_loop(self):
        """Receive transcript fragments from Deepgram."""
        try:
            async for raw_message in self._ws:
                try:
                    msg = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "Results":
                    channel = msg.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if not alternatives:
                        continue

                    best = alternatives[0]
                    text = best.get("transcript", "").strip()
                    if not text:
                        continue

                    is_final = msg.get("is_final", False)
                    # Deepgram provides start/duration in seconds
                    start_sec = msg.get("start", 0.0)
                    duration_sec = msg.get("duration", 0.0)
                    start_ms = int(start_sec * 1000)
                    end_ms = int((start_sec + duration_sec) * 1000)
                    confidence = best.get("confidence", 0.0)

                    await self.on_transcript(
                        text=text,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        is_final=is_final,
                        confidence=confidence,
                        speaker=self.speaker,
                    )

                elif msg_type == "Metadata":
                    logger.debug("Deepgram metadata for %s: %s", self.call_id,
                                 msg.get("request_id"))

                elif msg_type == "Error":
                    logger.error("Deepgram error for %s: %s", self.call_id, msg)

        except websockets.exceptions.ConnectionClosed:
            if not self._closed:
                logger.warning("Deepgram connection closed unexpectedly for %s", self.call_id)
        except asyncio.CancelledError:
            pass
