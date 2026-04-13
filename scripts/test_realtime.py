#!/usr/bin/env python3
"""Test the real-time insight pipeline end-to-end.

Publishes synthetic transcript chunks to Redis Streams and connects to
the broadcaster WebSocket to verify insights arrive in real time.

Usage:
    # Start evaluator and broadcaster first:
    #   python -m callisto.evaluator.consumer
    #   python -m callisto.broadcaster.server
    #
    # Then run this test:
    python scripts/test_realtime.py <tenant_id>

    # Or self-contained (starts everything in-process):
    python scripts/test_realtime.py --self-contained
"""

import asyncio
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:dev@localhost:5433/callisto")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")


async def publish_transcript_chunks(tenant_id: str, call_id: str):
    """Publish simulated transcript chunks to Redis Streams."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    stream_key = f"call:{call_id}:chunks"

    # Announce the stream
    await r.publish("callisto:active_streams", stream_key)
    await asyncio.sleep(0.5)  # give evaluator time to pick it up

    chunks = [
        {"text": "Hi thanks for calling, how can I help you today?", "start_ms": 0, "end_ms": 3000},
        {"text": "Yeah I've been having a lot of problems with my account.", "start_ms": 3000, "end_ms": 6000},
        {"text": "The service has been really unreliable this past month.", "start_ms": 6000, "end_ms": 9000},
        {"text": "I'm honestly thinking about switching to another provider.", "start_ms": 9000, "end_ms": 12000},
        {"text": "I've been a customer for three years but this is unacceptable.", "start_ms": 12000, "end_ms": 15000},
        {"text": "Can you tell me about your premium plan though?", "start_ms": 15000, "end_ms": 18000},
        {"text": "If the premium plan fixes these issues I might upgrade.", "start_ms": 18000, "end_ms": 21000},
        {"text": "But if not I'll probably just cancel at the end of the month.", "start_ms": 21000, "end_ms": 24000},
        {"text": "This is really frustrating, I've called three times about this.", "start_ms": 24000, "end_ms": 27000},
    ]

    print(f"Publishing {len(chunks)} transcript chunks to {stream_key}...")
    for i, chunk in enumerate(chunks):
        await r.xadd(stream_key, {
            "call_id": call_id,
            "tenant_id": tenant_id,
            "text": chunk["text"],
            "start_ms": str(chunk["start_ms"]),
            "end_ms": str(chunk["end_ms"]),
            "chunk_index": str(i),
            "speaker": "unknown",
            "confidence": "0.9",
            "type": "transcript",
        })
        print(f"  [{i}] {chunk['text'][:60]}")
        await asyncio.sleep(0.3)  # simulate real-time pacing

    # End marker
    await r.xadd(stream_key, {
        "call_id": call_id,
        "tenant_id": tenant_id,
        "text": "",
        "start_ms": "0",
        "end_ms": "0",
        "chunk_index": str(len(chunks)),
        "type": "end",
    })
    print("Published end-of-stream marker")
    await r.aclose()


async def listen_for_insights(call_id: str, timeout: float = 30.0):
    """Connect to the broadcaster and listen for insights."""
    import websockets

    url = f"ws://localhost:5311/ws/calls/{call_id}/live"
    print(f"\nListening for insights on {url}...")

    try:
        async with websockets.connect(url) as ws:
            deadline = time.time() + timeout
            insights = []
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    if data.get("type") == "insight":
                        insights.append(data)
                        print(f"\n  INSIGHT DETECTED:")
                        print(f"    Template: {data['template_name']}")
                        print(f"    Severity: {data['severity']}")
                        print(f"    Confidence: {data['confidence']:.2f}")
                        print(f"    Evidence: {data['evidence'][:80]}")
                        print(f"    Reasoning: {data['reasoning'][:80]}")
                    elif data.get("type") == "connected":
                        print(f"  Connected, watching: {data['watching']}")
                except asyncio.TimeoutError:
                    continue

            return insights
    except Exception as e:
        print(f"Could not connect to broadcaster: {e}")
        return []


async def run_self_contained():
    """Set up tenant/templates, start evaluator/broadcaster, run the test."""
    from callisto.app import create_app
    from callisto.extensions import db
    from callisto.models import InsightTemplate, Tenant, Call

    # Create tenant and templates
    app = create_app()
    with app.app_context():
        tenant = Tenant.query.filter_by(slug="realtime-test").first()
        if not tenant:
            tenant = Tenant(
                name="Realtime Test",
                slug="realtime-test",
                api_key_hash=hashlib.sha256(b"test").hexdigest(),
                settings={},
            )
            db.session.add(tenant)
            db.session.commit()

        existing = InsightTemplate.query.filter_by(tenant_id=tenant.id, active=True).all()
        if not existing:
            for td in [
                {"name": "Churn Intent", "prompt": "Detect if the caller wants to cancel, leave, or switch providers.", "category": "sales", "severity": "critical"},
                {"name": "Frustration", "prompt": "Detect if the caller expresses frustration or anger.", "category": "support", "severity": "warning"},
            ]:
                db.session.add(InsightTemplate(tenant_id=tenant.id, **td))
            db.session.commit()
            print("Created test templates")

        # Create a call record for this test
        call_id = f"test_realtime_{int(time.time())}"
        call = Call(
            tenant_id=tenant.id,
            external_id=call_id,
            source="test",
            direction="inbound",
            caller_number="+15550001111",
            status="active",
            started_at=db.func.now(),
            consent_given=True,
        )
        db.session.add(call)
        db.session.commit()

        tenant_id = str(tenant.id)

    print(f"Tenant: {tenant_id}")
    print(f"Call: {call_id}")

    # Start evaluator and broadcaster in background
    from callisto.evaluator.consumer import InsightEvaluator
    from callisto.broadcaster.server import main as broadcaster_main, handle_dashboard_ws, redis_subscriber
    import websockets

    evaluator = InsightEvaluator()
    evaluator_task = asyncio.create_task(evaluator.start())

    broadcaster_ws = await websockets.serve(handle_dashboard_ws, "localhost", 5311, max_size=2**16)
    subscriber_task = asyncio.create_task(redis_subscriber())

    print("Evaluator and broadcaster started")
    await asyncio.sleep(1)

    # Run publisher and listener concurrently
    publisher = asyncio.create_task(publish_transcript_chunks(tenant_id, call_id))
    listener = asyncio.create_task(listen_for_insights(call_id, timeout=20.0))

    await publisher
    insights = await listener

    print(f"\n=== Results: {len(insights)} real-time insights detected ===")

    # Check Postgres
    with app.app_context():
        from callisto.models import Insight
        db_insights = Insight.query.filter_by(call_id=call.id, source="realtime").all()
        print(f"Insights in database: {len(db_insights)}")
        for ins in db_insights:
            print(f"  - {ins.template.name}: {ins.confidence:.2f} — {ins.evidence[:60]}")

    # Cleanup
    evaluator_task.cancel()
    subscriber_task.cancel()
    broadcaster_ws.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--self-contained":
        asyncio.run(run_self_contained())
    elif len(sys.argv) > 1:
        tenant_id = sys.argv[1]
        call_id = f"test_rt_{int(time.time())}"
        asyncio.run(asyncio.gather(
            publish_transcript_chunks(tenant_id, call_id),
            listen_for_insights(call_id, timeout=30.0),
        ))
    else:
        print("Usage:")
        print("  python scripts/test_realtime.py --self-contained")
        print("  python scripts/test_realtime.py <tenant_id>")


if __name__ == "__main__":
    main()
