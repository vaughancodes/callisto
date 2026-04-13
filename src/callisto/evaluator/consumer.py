"""Real-time insight evaluator — Redis Streams consumer.

Consumes transcript chunks from Redis Streams, maintains a sliding context
window per call, and evaluates against tenant insight templates via the LLM.
Detected insights are persisted to Postgres and broadcast via Redis Pub/Sub.

Run directly:
    python -m callisto.evaluator.consumer

Each instance joins the 'evaluators' consumer group. Multiple instances can
run in parallel — Redis guarantees each chunk is processed by exactly one
consumer within the group.
"""

import asyncio
import json
import logging
import os
import time
import uuid

import redis.asyncio as aioredis
from openai import AsyncOpenAI

from callisto.config import Config
from callisto.evaluator.window import SlidingWindow, TranscriptChunk

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "evaluators"
STREAM_PATTERN = "call:*:chunks"
BROADCAST_CHANNEL = "insights:{call_id}"


class InsightEvaluator:
    """Consumes transcript chunks and evaluates for insights in real time."""

    def __init__(self):
        self.redis: aioredis.Redis | None = None
        self.llm = AsyncOpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
        )
        self.windows: dict[str, SlidingWindow] = {}
        self.templates_cache: dict[str, list[dict]] = {}  # tenant_id -> templates
        self.call_id_cache: dict[str, str] = {}  # external_id (call SID) -> db UUID
        # Track which templates have already fired per call to avoid duplicates.
        # Key: (call_id, template_id) -> last evidence string
        self.detected_cache: dict[tuple[str, str], str] = {}
        self.consumer_name = f"eval-{uuid.uuid4().hex[:8]}"

    async def start(self):
        redis_url = os.environ.get("REDIS_URL", Config.REDIS_URL)
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        logger.info("Evaluator %s connected to Redis", self.consumer_name)

        # Subscribe to new stream announcements
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("callisto:active_streams")

        # Track known streams
        active_streams: set[str] = set()

        # Find any existing streams
        async for key in self.redis.scan_iter(match="call:*:chunks", count=100):
            active_streams.add(key)
            await self._ensure_consumer_group(key)

        logger.info("Evaluator ready. Watching %d existing streams.", len(active_streams))

        # Run two loops: one listens for new stream announcements, one reads chunks
        await asyncio.gather(
            self._listen_for_new_streams(pubsub, active_streams),
            self._consume_loop(active_streams),
        )

    async def _listen_for_new_streams(self, pubsub, active_streams: set[str]):
        """Listen for announcements of new call streams."""
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            stream_key = message["data"]
            if stream_key not in active_streams:
                active_streams.add(stream_key)
                await self._ensure_consumer_group(stream_key)
                logger.info("Now tracking new stream: %s", stream_key)

    async def _ensure_consumer_group(self, stream_key: str):
        """Create the consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(
                stream_key, CONSUMER_GROUP, id="0", mkstream=True
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def _consume_loop(self, active_streams: set[str]):
        """Main loop: read chunks from all active streams."""
        while True:
            if not active_streams:
                await asyncio.sleep(0.5)
                continue

            # Build read dict: {stream_key: ">"}  — read new messages for this consumer
            streams = {s: ">" for s in active_streams}

            try:
                results = await self.redis.xreadgroup(
                    CONSUMER_GROUP,
                    self.consumer_name,
                    streams=streams,
                    count=10,
                    block=1000,  # block for 1s max
                )
            except aioredis.ResponseError as e:
                if "NOGROUP" in str(e):
                    # Group was destroyed (stream expired), re-create
                    for s in list(active_streams):
                        await self._ensure_consumer_group(s)
                    continue
                raise

            if not results:
                continue

            for stream_key, messages in results:
                for msg_id, data in messages:
                    try:
                        await self._process_chunk(stream_key, data)
                    except Exception:
                        logger.exception("Error processing chunk from %s", stream_key)

                    # Acknowledge the message
                    await self.redis.xack(stream_key, CONSUMER_GROUP, msg_id)

    async def _process_chunk(self, stream_key: str, data: dict):
        """Process a single transcript chunk."""
        call_id = data.get("call_id", "")
        tenant_id = data.get("tenant_id", "")
        text = data.get("text", "")
        msg_type = data.get("type", "transcript")

        # On end-of-stream, force-evaluate whatever's in the window then clean up
        if msg_type == "end":
            if call_id in self.windows and not self.windows[call_id].is_empty:
                templates = await self._get_templates(tenant_id)
                if templates:
                    await self._run_evaluation(call_id, tenant_id, self.windows[call_id], templates)
            self.cleanup_call(call_id)
            return

        if not text.strip():
            return

        chunk = TranscriptChunk(
            call_id=call_id,
            tenant_id=tenant_id,
            text=text,
            start_ms=int(data.get("start_ms", 0)),
            end_ms=int(data.get("end_ms", 0)),
            chunk_index=int(data.get("chunk_index", 0)),
            speaker=data.get("speaker", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
        )

        # Maintain sliding window per call
        if call_id not in self.windows:
            self.windows[call_id] = SlidingWindow(max_duration_ms=60000, eval_interval=1)

        window = self.windows[call_id]
        window.add(chunk)

        if not window.should_evaluate():
            return

        # Load templates for this tenant (cached)
        templates = await self._get_templates(tenant_id)
        if not templates:
            return

        await self._run_evaluation(call_id, tenant_id, window, templates)

    async def _run_evaluation(self, call_id: str, tenant_id: str,
                              window: SlidingWindow, templates: list[dict]):
        """Evaluate the current window and persist/broadcast any new insights."""
        window_text = window.get_text()
        if not window_text.strip():
            return

        detected = await self._evaluate_window(window_text, templates)

        db_call_id = self._resolve_call_id(call_id)
        if not db_call_id:
            logger.warning("Could not resolve call_id %s to a database UUID", call_id)
            return

        template_map = {t["id"]: t for t in templates}
        for det in detected:
            template_id = det.get("template_id", "")
            if template_id not in template_map:
                continue

            evidence = det.get("evidence", "").strip()
            dedup_key = (call_id, template_id)
            past_evidence = self.detected_cache.get(dedup_key, set())
            # Skip if evidence overlaps with any previously detected evidence
            # (substring match in either direction catches sliding window growth)
            if evidence and past_evidence:
                is_dup = False
                for prev in past_evidence:
                    if evidence in prev or prev in evidence:
                        is_dup = True
                        # Keep the longer evidence string
                        if len(evidence) > len(prev):
                            past_evidence.discard(prev)
                            past_evidence.add(evidence)
                        break
                if is_dup:
                    logger.debug("Skipping overlapping evidence for %s: %s",
                                 template_map[template_id]["name"], evidence[:60])
                    continue
            if dedup_key not in self.detected_cache:
                self.detected_cache[dedup_key] = set()
            self.detected_cache[dedup_key].add(evidence)

            insight_id = str(uuid.uuid4())

            self._persist_insight(
                insight_id=insight_id,
                call_id=db_call_id,
                tenant_id=tenant_id,
                template_id=template_id,
                confidence=det.get("confidence", 0.0),
                evidence=det.get("evidence", ""),
                reasoning=det.get("reasoning", ""),
                transcript_range=window.get_range(),
            )

            await self._broadcast_insight(
                call_id=call_id,
                insight_id=insight_id,
                template_name=template_map[template_id]["name"],
                template_id=template_id,
                confidence=det.get("confidence", 0.0),
                evidence=det.get("evidence", ""),
                reasoning=det.get("reasoning", ""),
                severity=template_map[template_id].get("severity", "info"),
            )

    def _resolve_call_id(self, external_id: str) -> str | None:
        """Map an external call SID (e.g. Twilio CA...) to the database UUID."""
        if external_id in self.call_id_cache:
            return self.call_id_cache[external_id]

        from callisto.app import create_app
        from callisto.models import Call

        app = create_app()
        with app.app_context():
            call = Call.query.filter_by(external_id=external_id).first()
            if call:
                db_id = str(call.id)
                self.call_id_cache[external_id] = db_id
                return db_id
        return None

    async def _get_templates(self, tenant_id: str) -> list[dict]:
        """Load active realtime templates for a tenant, with caching."""
        if tenant_id in self.templates_cache:
            return self.templates_cache[tenant_id]

        from callisto.app import create_app
        from callisto.models import InsightTemplate

        app = create_app()
        with app.app_context():
            templates = InsightTemplate.query.filter_by(
                tenant_id=tenant_id, active=True, is_realtime=True
            ).all()
            result = [
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

        self.templates_cache[tenant_id] = result
        return result

    async def _evaluate_window(self, window_text: str, templates: list[dict]) -> list[dict]:
        """Run LLM evaluation on the current window text."""
        template_descriptions = "\n".join(
            f"- Template ID: {t['id']}\n"
            f"  Name: {t['name']}\n"
            f"  Severity: {t['severity']}\n"
            f"  Detection criteria: {t['prompt']}"
            for t in templates
        )

        prompt = f"""You are a real-time call analyst. Evaluate this transcript excerpt against the insight templates. This is a LIVE call — only report insights clearly present in the text.

## Templates
{template_descriptions}

## Transcript (last ~60 seconds)
{window_text}

Respond with a JSON array. For each template:
- "template_id": the template ID
- "detected": true/false
- "confidence": 0.0-1.0
- "evidence": exact quote if detected, empty string if not
- "reasoning": brief explanation

Only include templates where detected is true. If nothing is detected, respond with an empty array [].

Respond ONLY with the JSON array."""

        try:
            response = await self.llm.chat.completions.create(
                model=Config.LLM_MODEL,
                temperature=0.1,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            logger.exception("LLM evaluation failed")
            return []

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        try:
            results = json.loads(text)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response: %s", text[:200])
            return []

        detected = [r for r in results if r.get("detected")]
        if detected:
            logger.info("Real-time evaluation: %d insights detected", len(detected))
        return detected

    def _persist_insight(self, *, insight_id, call_id, tenant_id, template_id,
                         confidence, evidence, reasoning, transcript_range):
        """Write an insight to Postgres."""
        from callisto.app import create_app
        from callisto.extensions import db
        from callisto.models import Insight

        app = create_app()
        with app.app_context():
            insight = Insight(
                id=uuid.UUID(insight_id),
                call_id=call_id,
                tenant_id=tenant_id,
                template_id=template_id,
                source="realtime",
                confidence=float(confidence),
                evidence=evidence,
                result={"reasoning": reasoning},
                transcript_range=transcript_range,
            )
            db.session.add(insight)
            db.session.commit()
            logger.info("Persisted realtime insight %s for call %s", insight_id, call_id)

    async def _broadcast_insight(self, *, call_id, insight_id, template_name,
                                  template_id, confidence, evidence, reasoning, severity):
        """Publish insight to Redis Pub/Sub for WebSocket broadcaster."""
        message = json.dumps({
            "type": "insight",
            "call_id": call_id,
            "insight_id": insight_id,
            "template_id": template_id,
            "template_name": template_name,
            "confidence": confidence,
            "evidence": evidence,
            "reasoning": reasoning,
            "severity": severity,
            "timestamp": time.time(),
        })
        channel = f"insights:{call_id}"
        await self.redis.publish(channel, message)
        # Also publish to a global channel for dashboards watching all calls
        await self.redis.publish("insights:all", message)
        logger.info("Broadcast insight %s on %s", template_name, channel)

    def cleanup_call(self, call_id: str):
        """Remove state for a completed call."""
        self.windows.pop(call_id, None)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    evaluator = InsightEvaluator()
    await evaluator.start()


if __name__ == "__main__":
    asyncio.run(main())
