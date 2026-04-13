#!/usr/bin/env python3
"""End-to-end pipeline test.

Creates a tenant with insight templates, synthesizes a test audio file with
speech-like content, then runs the transcription and evaluation pipeline
directly (bypassing VoIP.ms download). Verifies results in Postgres.

Usage:
    LLM_API_KEY=sk-... python scripts/test_pipeline.py

Requires a running Postgres instance (docker compose up postgres).
"""

import os
import sys
import wave
import struct
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:dev@localhost:5433/callisto")


def main():
    from callisto.app import create_app
    from callisto.extensions import db
    from callisto.models import Call, Insight, InsightTemplate, Tenant, Transcript

    app = create_app()

    with app.app_context():
        print("=== Callisto Pipeline End-to-End Test ===\n")

        # 1. Create a test tenant
        import hashlib
        tenant = Tenant.query.filter_by(slug="test-pipeline").first()
        if not tenant:
            tenant = Tenant(
                name="Pipeline Test Corp",
                slug="test-pipeline",
                api_key_hash=hashlib.sha256(b"test-key").hexdigest(),
                settings={"whisper_model": "tiny"},
            )
            db.session.add(tenant)
            db.session.commit()
            print(f"Created tenant: {tenant.name} ({tenant.id})")
        else:
            print(f"Using existing tenant: {tenant.name} ({tenant.id})")

        # 2. Create insight templates
        existing_templates = InsightTemplate.query.filter_by(
            tenant_id=tenant.id, active=True
        ).all()
        if not existing_templates:
            templates_data = [
                {
                    "name": "Churn Intent",
                    "prompt": "Detect if the caller expresses intent to cancel, leave, switch providers, or stop using the service.",
                    "category": "sales",
                    "severity": "critical",
                },
                {
                    "name": "Upsell Opportunity",
                    "prompt": "Detect if the caller expresses interest in additional features, upgrades, or expanded service.",
                    "category": "sales",
                    "severity": "info",
                },
                {
                    "name": "Frustration / Complaint",
                    "prompt": "Detect if the caller expresses frustration, anger, or makes a complaint about the service or experience.",
                    "category": "support",
                    "severity": "warning",
                },
            ]
            for td in templates_data:
                t = InsightTemplate(tenant_id=tenant.id, **td)
                db.session.add(t)
            db.session.commit()
            print(f"Created {len(templates_data)} insight templates")
        else:
            print(f"Using {len(existing_templates)} existing templates")

        # 3. Create a test call record
        from datetime import datetime
        call = Call(
            tenant_id=tenant.id,
            external_id="test-pipeline-001",
            source="test",
            direction="inbound",
            caller_number="+15551234567",
            status="processing",
            started_at=datetime.now(),
            consent_given=True,
        )
        db.session.add(call)
        db.session.commit()
        print(f"Created call: {call.id}")

        # 4. Test transcription with a real audio file
        print("\n--- Transcription ---")
        # We'll use the TTS-generated test or a silence file.
        # For a real test, place a .wav file at /tmp/callisto_test.wav
        test_audio = os.environ.get("TEST_AUDIO_PATH")
        if test_audio and os.path.exists(test_audio):
            print(f"Using provided audio: {test_audio}")
            from callisto.transcription.whisper import transcribe_audio
            segments = transcribe_audio(test_audio, model_name="tiny")
        else:
            print("No TEST_AUDIO_PATH provided — using synthetic transcript")
            # Simulate what Whisper would return
            segments = [
                {"text": "Hi, I'm calling because I've been having a lot of issues with my account lately.", "start_ms": 0, "end_ms": 5000, "confidence": -0.3, "chunk_index": 0},
                {"text": "I've been a customer for three years but honestly I'm thinking about switching to another provider.", "start_ms": 5000, "end_ms": 10000, "confidence": -0.25, "chunk_index": 1},
                {"text": "The service has been really unreliable this past month and I'm pretty frustrated.", "start_ms": 10000, "end_ms": 15000, "confidence": -0.28, "chunk_index": 2},
                {"text": "I saw that you have a premium plan though. What does that include?", "start_ms": 15000, "end_ms": 20000, "confidence": -0.22, "chunk_index": 3},
                {"text": "If the premium plan can fix these reliability issues I might be interested in upgrading.", "start_ms": 20000, "end_ms": 25000, "confidence": -0.2, "chunk_index": 4},
                {"text": "But if not, I'll probably just cancel my account at the end of the month.", "start_ms": 25000, "end_ms": 30000, "confidence": -0.3, "chunk_index": 5},
            ]

        # Store transcript chunks
        import math
        for seg in segments:
            chunk = Transcript(
                call_id=call.id,
                tenant_id=tenant.id,
                speaker="unknown",
                text=seg["text"],
                start_ms=seg["start_ms"],
                end_ms=seg["end_ms"],
                confidence=max(0.0, min(1.0, math.exp(seg["confidence"]))),
                chunk_index=seg["chunk_index"],
            )
            db.session.add(chunk)
        db.session.commit()
        print(f"Stored {len(segments)} transcript chunks")

        full_transcript = " ".join(s["text"] for s in segments)
        print(f"Transcript: {full_transcript[:200]}...")

        # 5. Test insight evaluation
        print("\n--- Insight Evaluation ---")
        api_key = os.environ.get("LLM_API_KEY", "")
        if not api_key:
            print("LLM_API_KEY not set — skipping LLM evaluation")
            print("Set LLM_API_KEY (and optionally LLM_BASE_URL, LLM_MODEL) to test the full pipeline")
            call.status = "completed"
            db.session.commit()
        else:
            from callisto.evaluation.insights import evaluate_transcript

            templates = InsightTemplate.query.filter_by(
                tenant_id=tenant.id, active=True
            ).all()
            template_dicts = [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "description": t.description or "",
                    "prompt": t.prompt,
                    "category": t.category,
                    "severity": t.severity,
                }
                for t in templates
            ]

            detected = evaluate_transcript(full_transcript, template_dicts)

            template_map = {str(t.id): t for t in templates}
            for det in detected:
                template_id = det["template_id"]
                if template_id not in template_map:
                    print(f"  WARNING: Unknown template_id {template_id}")
                    continue

                insight = Insight(
                    call_id=call.id,
                    tenant_id=tenant.id,
                    template_id=template_map[template_id].id,
                    source="post_call",
                    confidence=float(det.get("confidence", 0.0)),
                    evidence=det.get("evidence", ""),
                    result={"reasoning": det.get("reasoning", ""), "raw": det},
                )
                db.session.add(insight)

            call.status = "completed"
            db.session.commit()
            print(f"Detected {len(detected)} insights:")
            for d in detected:
                tid = d["template_id"]
                name = template_map.get(tid)
                name = name.name if name else tid[:8]
                print(f"  [{name}] confidence={d['confidence']:.2f}")
                print(f"    evidence: {d['evidence'][:100]}")
                print(f"    reasoning: {d['reasoning'][:100]}")

        # 6. Verify results in the database
        print("\n--- Database Verification ---")
        stored_chunks = Transcript.query.filter_by(call_id=call.id).count()
        stored_insights = Insight.query.filter_by(call_id=call.id).count()
        call_status = db.session.get(Call, call.id).status

        print(f"Call status: {call_status}")
        print(f"Transcript chunks: {stored_chunks}")
        print(f"Insights detected: {stored_insights}")

        # List insights from DB
        if stored_insights > 0:
            insights = Insight.query.filter_by(call_id=call.id).all()
            for ins in insights:
                print(f"  - {ins.template.name}: confidence={ins.confidence:.2f}, evidence={ins.evidence[:80]}...")

        print("\n=== Pipeline test complete ===")


if __name__ == "__main__":
    main()
