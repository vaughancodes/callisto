#!/usr/bin/env python3
"""Simulate a Twilio Media Stream WebSocket session against the ingestion server.

This sends realistic Twilio-format WebSocket messages (connected, start, media,
stop) to verify the full ingestion pipeline works end-to-end.

Usage:
    # Terminal 1: start the ingestion server
    python -m callisto.ingestion.server

    # Terminal 2: run this test (after creating a tenant)
    python scripts/test_twilio_stream.py <tenant_id>

Or run in self-contained mode (starts server, sends stream, checks DB):
    python scripts/test_twilio_stream.py --self-contained
"""

import asyncio
import base64
import json
import math
import os
import struct
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:dev@localhost:5433/callisto")


def generate_mulaw_silence(n_bytes: int) -> bytes:
    """Generate n_bytes of mulaw-encoded silence (0xFF = mulaw zero)."""
    return bytes([0xFF] * n_bytes)


def generate_mulaw_tone(n_bytes: int, freq_hz: float = 440.0, sample_rate: int = 8000) -> bytes:
    """Generate n_bytes of mulaw-encoded sine tone for testing."""
    samples = []
    for i in range(n_bytes):
        # Generate 16-bit PCM sine wave
        t = i / sample_rate
        pcm_val = int(32767 * 0.5 * math.sin(2 * math.pi * freq_hz * t))
        # Simple PCM → mulaw encoding (approximate)
        sign = 0x80 if pcm_val >= 0 else 0
        pcm_val = abs(pcm_val)
        pcm_val = min(pcm_val, 32635)
        pcm_val += 0x84
        exponent = 7
        for exp in range(7, -1, -1):
            if pcm_val >= (1 << (exp + 3)):
                exponent = exp
                break
        mantissa = (pcm_val >> (exponent + 3)) & 0x0F
        mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
        samples.append(mulaw_byte)
    return bytes(samples)


async def simulate_twilio_stream(ws_url: str, tenant_id: str, duration_sec: float = 3.0):
    """Connect to the ingestion server and send a simulated Twilio Media Stream."""
    import websockets

    call_sid = f"CA_test_{int(time.time())}"
    stream_sid = f"MZ_test_{int(time.time())}"

    print(f"Connecting to {ws_url}...")
    async with websockets.connect(ws_url) as ws:
        # 1. Send 'connected' message
        await ws.send(json.dumps({
            "event": "connected",
            "protocol": "Call",
            "version": "1.0.0",
        }))
        print("Sent: connected")

        # 2. Send 'start' message
        await ws.send(json.dumps({
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": stream_sid,
                "accountSid": "AC_test",
                "callSid": call_sid,
                "tracks": ["inbound"],
                "customParameters": {
                    "tenant_id": tenant_id,
                    "from": "+15550001111",
                    "to": "+15551234567",
                    "direction": "inbound",
                },
                "mediaFormat": {
                    "encoding": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "channels": 1,
                },
            },
        }))
        print(f"Sent: start (call_sid={call_sid})")

        # 3. Send 'media' messages — 20ms frames (160 bytes of mulaw @ 8kHz)
        frame_size = 160  # 20ms at 8kHz
        n_frames = int(duration_sec * 1000 / 20)
        seq = 2

        for i in range(n_frames):
            # Alternate between tone and silence to simulate speech
            if (i // 25) % 2 == 0:  # ~500ms tone
                audio = generate_mulaw_tone(frame_size, freq_hz=300 + (i % 10) * 50)
            else:
                audio = generate_mulaw_silence(frame_size)

            payload = base64.b64encode(audio).decode()

            await ws.send(json.dumps({
                "event": "media",
                "sequenceNumber": str(seq),
                "media": {
                    "track": "inbound",
                    "chunk": str(i + 1),
                    "timestamp": str(i * 20),
                    "payload": payload,
                },
            }))
            seq += 1

            # Simulate real-time pacing (slightly faster for testing)
            await asyncio.sleep(0.005)

        print(f"Sent: {n_frames} media frames ({duration_sec}s of audio)")

        # 4. Send 'stop' message
        await ws.send(json.dumps({
            "event": "stop",
            "sequenceNumber": str(seq),
            "stop": {
                "accountSid": "AC_test",
                "callSid": call_sid,
            },
        }))
        print(f"Sent: stop")

        # Give the server a moment to process
        await asyncio.sleep(1)

    return call_sid


def check_database(call_sid: str):
    """Verify the call was recorded in the database."""
    from callisto.app import create_app
    from callisto.models import Call

    app = create_app()
    with app.app_context():
        call = Call.query.filter_by(external_id=call_sid).first()
        if call:
            print(f"\nDatabase check:")
            print(f"  Call ID: {call.id}")
            print(f"  Status: {call.status}")
            print(f"  Duration: {call.duration_sec}s")
            print(f"  Stream SID: {call.stream_sid}")
            print(f"  Source: {call.source}")
            return True
        else:
            print(f"\nWARNING: No call record found for call_sid={call_sid}")
            return False


async def run_self_contained():
    """Start the server, run the test, check the DB."""
    import hashlib
    from callisto.app import create_app
    from callisto.extensions import db
    from callisto.models import Tenant

    app = create_app()
    with app.app_context():
        tenant = Tenant.query.filter_by(slug="stream-test").first()
        if not tenant:
            tenant = Tenant(
                name="Stream Test",
                slug="stream-test",
                api_key_hash=hashlib.sha256(b"test").hexdigest(),
                settings={"whisper_model": "tiny"},
            )
            db.session.add(tenant)
            db.session.commit()
        tenant_id = str(tenant.id)

    # Start ingestion server in background
    from callisto.ingestion.server import handle_twilio_stream
    import websockets

    port = int(os.environ.get("TEST_WS_PORT", "8766"))
    server = await websockets.serve(handle_twilio_stream, "localhost", port, max_size=2**20)
    print(f"Ingestion server started on ws://localhost:{port}")

    try:
        call_sid = await simulate_twilio_stream(
            f"ws://localhost:{port}/ws/twilio/stream",
            tenant_id,
            duration_sec=2.0,
        )
        check_database(call_sid)
    finally:
        server.close()
        await server.wait_closed()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--self-contained":
        asyncio.run(run_self_contained())
    elif len(sys.argv) > 1:
        tenant_id = sys.argv[1]
        ws_url = os.environ.get("WS_URL", "ws://localhost:8765/ws/twilio/stream")
        call_sid = asyncio.run(simulate_twilio_stream(ws_url, tenant_id))
        check_database(call_sid)
    else:
        print("Usage:")
        print("  python scripts/test_twilio_stream.py <tenant_id>")
        print("  python scripts/test_twilio_stream.py --self-contained")
        sys.exit(1)


if __name__ == "__main__":
    main()
