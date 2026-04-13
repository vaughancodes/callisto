# Callisto

**Multi-tenant telephony intelligence platform — real-time call analysis with configurable LLM-powered insight detection.**

A backend system that listens to phone calls, transcribes audio in real time, and uses an LLM to detect configurable insights for businesses monitoring client communications.

**Stack:** Python (Flask/SQLAlchemy), Celery, PostgreSQL, Redis Streams, WebSockets

---

## Table of Contents

1. [Project Context](#project-context)
2. [System Overview](#system-overview)
3. [Architecture Diagram](#architecture-diagram)
4. [Data Models](#data-models)
5. [Service Boundaries](#service-boundaries)
6. [Hot Path — Real-Time Pipeline](#hot-path--real-time-pipeline)
7. [Cold Path — Post-Call Analysis](#cold-path--post-call-analysis)
8. [Integration Layer — Audio Ingestion](#integration-layer--audio-ingestion)
9. [API Surface](#api-surface)
10. [Infrastructure](#infrastructure)
11. [Legal & Compliance](#legal--compliance)
12. [MVP Phases](#mvp-phases)
13. [Cost Considerations](#cost-considerations)
14. [Competitive Landscape](#competitive-landscape)

---

## Project Context

### What This Is

A platform that allows businesses to gain insight into communications and intent of their clients. Companies provide a list of insights to look for (churn intent, upsell opportunity, compliance violations, etc.) and the system evaluates live or recorded calls against those templates, surfacing results in real time or in post-call reports.

This is a serious distributed systems project, not a thin LLM wrapper. The engineering complexity lives in async pipelines, multi-tenant isolation, streaming audio processing, and real-time delivery.

### Telephony Setup

Twilio is the primary telephony provider for development and the first production integration. Twilio's Media Streams API forks live call audio and streams it over WebSockets in real time — this is the core ingestion mechanism.

Twilio provides:
- Media Streams: real-time audio forking over WebSockets via `<Start><Stream>` TwiML
- Bidirectional streams for potential future agent assist features
- Phone numbers (DIDs) for development and testing via free trial credits
- Call lifecycle webhooks (call start, end, status changes)
- Both inbound and outbound track streaming (`inbound_track`, `outbound_track`, `both_tracks`)
- Base64-encoded mulaw audio at 8kHz in the media stream payloads

The platform is designed to be provider-agnostic — Twilio is the first adapter, but the architecture supports adding RingCentral, Dialpad, Zoom Phone, or raw SIP integrations later via the same provider adapter interface.

### Development Approach

Phase 1 uses Twilio Media Streams for live audio ingestion from the start. When a call hits a Twilio number, the `<Start><Stream>` TwiML instruction forks the audio to a WebSocket endpoint the platform controls. The audio flows through the transcription and insight pipeline in real time.

For transcription:
- **Hot path / streaming:** Deepgram free tier for low-latency streaming transcription (generous development runway)
- **Cold path / batch:** Whisper.cpp on CPU (free, for post-call re-transcription if needed)
- Self-hosted Whisper is viable for the hot path but requires a GPU for real-time speed

### Twilio Media Streams — Key Technical Details

Twilio sends WebSocket messages in the following format:

- **connected**: First message when WebSocket is established, describes the protocol
- **start**: Contains stream metadata — call SID, account SID, custom parameters, track info
- **media**: Raw audio data, base64-encoded mulaw at 8kHz. The `payload` field contains the audio, `timestamp` tracks position, `chunk` is a sequence number
- **stop**: Sent when the stream ends (call ended or `<Stop><Stream>` executed)

Audio format from Twilio: **mulaw encoding, 8kHz sample rate, single channel**. This needs to be decoded and potentially resampled (to 16kHz PCM) before feeding to transcription services that expect higher quality input.

For unidirectional streams (our primary use case), you can stream up to 4 tracks simultaneously per call. For bidirectional streams, only 1 stream per call is allowed.

The ingestion gateway must accept incoming WSS connections from Twilio. In development, use ngrok to expose a local WebSocket endpoint. In production, the ingestion gateway is a publicly accessible service behind a load balancer.

---

## System Overview

The system has two distinct processing paths:

- **Hot path:** Real-time insight delivery during live calls. Latency target: <8 seconds speech-to-insight. Uses Redis Streams for low-latency message passing.
- **Cold path:** Post-call deep analysis, reporting, and trend aggregation. Uses Celery for task orchestration. No latency pressure.

This separation is critical — the hot path must never block on heavy analysis.

---

## Architecture Diagram

```
                      ┌─────────────────────────────────────────────────┐
                      │              INGESTION LAYER                     │
                      │                                                 │
  ┌──────────┐        │   ┌───────────────────────────────────────┐     │
  │ Twilio   │──WSS──▶│   │  Twilio Media Stream Handler         │     │
  │ Media    │        │   │  • Accept WebSocket connections       │     │
  │ Streams  │        │   │  • Decode base64 mulaw audio          │     │
  └──────────┘        │   │  • Resample 8kHz → 16kHz PCM          │     │
                      │   │  • Buffer into chunks                 │     │
  ┌──────────┐        │   └──────────────────┬────────────────────┘     │
  │ Future:  │        │                      │                          │
  │ SIP/RTC  │──???──▶│   ┌──────────────────▼────────────────────┐     │
  │ Adapters │        │   │  Unified Audio Stream Buffer           │     │
  └──────────┘        │   │  (per-channel ring buffer)             │     │
                      │   └──────────────────┬────────────────────┘     │
                      └──────────────────────┼──────────────────────────┘
                                             │
                      ┌──────────────────────┼──────────────────────────┐
                      │         HOT PATH     │    (real-time)           │
                      │                      ▼                          │
                      │   ┌─────────────────────────────────────┐       │
                      │   │   Streaming Transcription Service   │       │
                      │   │   (Deepgram streaming WebSocket)    │       │
                      │   └──────────────────┬──────────────────┘       │
                      │                      │                          │
                      │                      ▼                          │
                      │   ┌─────────────────────────────────────┐       │
                      │   │   Redis Stream: call:{id}:chunks    │       │
                      │   └──────────────────┬──────────────────┘       │
                      │                      │                          │
                      │                      ▼                          │
                      │   ┌─────────────────────────────────────┐       │
                      │   │   Insight Evaluator (consumer)      │       │
                      │   │   • Sliding context window          │       │
                      │   │   • Tenant insight templates        │       │  ┌────────────┐
                      │   │   • LLM evaluation w/ structured   │──ws──▶│  │  Agent UI  │
                      │   │     output                          │       │  │  Dashboard │
                      │   └─────────────────────────────────────┘       │  └────────────┘
                      └────────────────────────────────────────────────┘

                      ┌────────────────────────────────────────────────┐
                      │         COLD PATH    (post-call)               │
                      │                                                │
                      │   ┌──────────────┐    ┌─────────────────────┐  │
                      │   │ Twilio       │───▶│  Celery Task:       │  │
                      │   │ call-end     │    │  full_analysis      │  │
                      │   │ webhook      │    │  • Full transcript  │  │
                      │   └──────────────┘    │  • Deep LLM pass    │  │
                      │                       │  • Insight scoring   │  │
                      │                       │  • Summary gen      │  │  ┌────────────┐
                      │                       │  • Trend tagging    │─▶│  │  Postgres  │
                      │                       └─────────────────────┘  │  └────────────┘
                      └────────────────────────────────────────────────┘
```

### Service Dependency Graph

```
┌──────────┐       ┌──────────────┐       ┌───────────────┐
│ API      │──────▶│  PostgreSQL   │◀──────│  Analysis     │
│ Service  │       │              │       │  Workers      │
└──────────┘       └──────┬───────┘       └───────┬───────┘
                          │                       │
                          │                       │ (celery broker)
                   ┌──────▼───────┐               │
                   │    Redis     │◀──────────────┘
                   │  Streams +   │
                   │  Pub/Sub     │
                   └──┬───────┬──┘
                      │       │
            ┌─────────▼┐   ┌─▼──────────┐
            │ Insight   │   │ WebSocket  │
            │ Evaluator │──▶│ Broadcaster│───▶ Agent dashboards
            └───────────┘   └────────────┘
                  ▲
                  │
            ┌─────┴────────┐
            │ Transcription │
            │ Service       │
            └──────▲────────┘
                   │
            ┌──────┴────────┐
            │  Ingestion    │◀─── Twilio Media Streams (WSS)
            │  Gateway      │◀─── Twilio Webhooks (HTTP)
            └───────────────┘
```

---

## Data Models

Multi-tenancy is column-based with `tenant_id` on every table, enforced at the query layer via SQLAlchemy session events. Row-level security in Postgres as a second layer of defense.

```python
class Tenant(Base):
    __tablename__ = "tenants"
    id            = Column(UUID, primary_key=True, default=uuid4)
    name          = Column(String, nullable=False)
    slug          = Column(String, unique=True, index=True)
    settings      = Column(JSONB, default={})  # transcription provider prefs, LLM model, etc.
    api_key_hash  = Column(String, nullable=False)
    created_at    = Column(DateTime, server_default=func.now())


class InsightTemplate(Base):
    """What the tenant wants to detect in calls."""
    __tablename__ = "insight_templates"
    id            = Column(UUID, primary_key=True, default=uuid4)
    tenant_id     = Column(UUID, ForeignKey("tenants.id"), index=True)
    name          = Column(String)            # "Churn Intent", "Upsell Opportunity", "Compliance: HIPAA"
    description   = Column(Text)              # Human-readable description
    prompt        = Column(Text)              # LLM evaluation prompt
    category      = Column(String)            # "sales", "compliance", "support", "custom"
    severity      = Column(String)            # "info", "warning", "critical"
    is_realtime   = Column(Boolean, default=True)  # evaluate on hot path?
    output_schema = Column(JSONB)             # expected structured output shape
    active        = Column(Boolean, default=True)


class Contact(Base):
    """Known contacts for a tenant — matched against incoming call numbers."""
    __tablename__ = "contacts"
    id                = Column(UUID, primary_key=True, default=uuid4)
    tenant_id         = Column(UUID, ForeignKey("tenants.id"), index=True)
    name              = Column(String, nullable=False)
    company           = Column(String, nullable=True)
    phone_numbers     = Column(JSONB, default=[])       # array of E.164 strings ["+15551234567"]
    email             = Column(String, nullable=True)
    google_contact_id = Column(String, nullable=True)   # for Google Contacts sync dedup
    metadata          = Column(JSONB, default={})
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Call(Base):
    __tablename__ = "calls"
    id            = Column(UUID, primary_key=True, default=uuid4)
    tenant_id     = Column(UUID, ForeignKey("tenants.id"), index=True)
    contact_id    = Column(UUID, ForeignKey("contacts.id"), nullable=True)  # matched contact
    external_id   = Column(String, index=True)  # Twilio Call SID
    stream_sid    = Column(String, nullable=True)  # Twilio Media Stream SID
    source        = Column(String)              # "twilio", "sip_direct", etc.
    direction     = Column(String)              # "inbound", "outbound"
    caller_number = Column(String)
    callee_number = Column(String)
    agent_id      = Column(String, nullable=True)
    status        = Column(String, default="active")  # active, completed, failed
    started_at    = Column(DateTime)
    ended_at      = Column(DateTime, nullable=True)
    duration_sec  = Column(Integer, nullable=True)
    consent_given = Column(Boolean, default=False)
    metadata      = Column(JSONB, default={})


class Transcript(Base):
    __tablename__ = "transcripts"
    id            = Column(UUID, primary_key=True, default=uuid4)
    call_id       = Column(UUID, ForeignKey("calls.id"), index=True)
    tenant_id     = Column(UUID, ForeignKey("tenants.id"), index=True)
    speaker       = Column(String)            # "agent", "caller", "unknown"
    text          = Column(Text)
    start_ms      = Column(Integer)           # offset from call start
    end_ms        = Column(Integer)
    confidence    = Column(Float)
    chunk_index   = Column(Integer)           # ordering within the call


class Insight(Base):
    __tablename__ = "insights"
    id            = Column(UUID, primary_key=True, default=uuid4)
    call_id       = Column(UUID, ForeignKey("calls.id"), index=True)
    tenant_id     = Column(UUID, ForeignKey("tenants.id"), index=True)
    template_id   = Column(UUID, ForeignKey("insight_templates.id"))
    source        = Column(String)            # "realtime" or "post_call"
    detected_at   = Column(DateTime)
    confidence    = Column(Float)             # 0.0 - 1.0
    evidence      = Column(Text)              # the transcript excerpt that triggered it
    result        = Column(JSONB)             # structured output from LLM
    transcript_range = Column(JSONB)          # {start_chunk: N, end_chunk: M}


class CallSummary(Base):
    __tablename__ = "call_summaries"
    id            = Column(UUID, primary_key=True, default=uuid4)
    call_id       = Column(UUID, ForeignKey("calls.id"), unique=True)
    tenant_id     = Column(UUID, ForeignKey("tenants.id"), index=True)
    summary       = Column(Text)
    sentiment     = Column(String)            # "positive", "negative", "neutral", "mixed"
    key_topics    = Column(JSONB)             # ["billing", "cancellation", "product_feedback"]
    action_items  = Column(JSONB)             # [{text: "...", assignee: "agent", priority: "high"}]
    llm_model     = Column(String)            # which model produced this
    token_cost    = Column(Integer)           # total tokens consumed
    created_at    = Column(DateTime, server_default=func.now())
```

**Design decisions:**
- Transcript chunks are stored individually rather than as a single blob. This lets you query for insights with direct links back to the exact moment in the call, enables speaker-level analytics, and supports the sliding window pattern on the hot path without re-tokenizing the full transcript.
- Contacts store phone numbers as a JSONB array of E.164 strings. When a call comes in, the ingestion gateway does a phone number lookup against the tenant's contacts and attaches the `contact_id` to the Call record. The dashboard then shows contact name/company instead of raw phone numbers.
- Contacts can be populated via CSV import (with configurable column mappings), manual CRUD, or Google Contacts sync (using the People API via the same OAuth session). Google sync upserts on `google_contact_id` first, then falls back to phone number matching.

---

## Service Boundaries

Five distinct services, each independently deployable. In the MVP, they all run as processes in a single Docker Compose stack. In production on K8s, they scale independently.

### 1. API Service (Flask)

REST API for tenant management, insight template CRUD, call history queries, and reporting endpoints. Handles API key auth, request validation, pagination. Also serves the Twilio webhook endpoints for call lifecycle events. Standard Flask + SQLAlchemy.

### 2. Ingestion Gateway (async WebSocket server)

Accepts incoming WebSocket connections from Twilio Media Streams. Each active call gets one WebSocket connection. The handler:
1. Receives the `start` message with call metadata (Call SID, custom parameters including tenant ID)
2. Creates a Call record in Postgres
3. Opens a streaming WebSocket connection to Deepgram for this call
4. Receives `media` messages containing base64-encoded mulaw audio
5. Decodes mulaw → PCM, resamples 8kHz → 16kHz
6. Forwards decoded PCM to Deepgram in real time
7. Receives transcript fragments from Deepgram, publishes to Redis Streams and Postgres
8. Accumulates all PCM for WAV export
9. On `stop` message, closes Deepgram connection and triggers the cold path analysis chain

This is a standalone async Python process (using `websockets` library), NOT a Celery worker — it needs to maintain persistent WebSocket connections to both Twilio and Deepgram.

### 3. Transcription Service (pluggable: Deepgram or Whisper)

The ingestion gateway supports two real-time STT providers, selected via the `STT_PROVIDER` env var (`"auto"` by default — uses Deepgram if `DEEPGRAM_API_KEY` is set, otherwise Whisper). If Deepgram fails to connect, it falls back to Whisper automatically.

**Deepgram streaming** (`STT_PROVIDER=deepgram`): Opens a streaming WebSocket to Deepgram's Nova-2 API per call. Decoded 16kHz PCM is forwarded in real time. Deepgram returns final transcript fragments with timestamps and confidence scores, typically within ~300ms of speech. Configuration: `encoding=linear16`, `sample_rate=16000`, `model=nova-2`, `punctuate=true`, `interim_results=true`, `endpointing=300ms`, `utterance_end_ms=1500ms`.

**Whisper batched** (`STT_PROVIDER=whisper`): Accumulates audio into segments (default 10 seconds, configurable via `WHISPER_SEGMENT_SECONDS`), writes a temp WAV, and runs Whisper transcription. Supports two modes:
- **Local** (default): runs openai-whisper in-process. Model size controlled by `WHISPER_MODEL` (tiny/base/small/medium/large).
- **Remote**: set `WHISPER_API_URL` to point at any OpenAI-compatible `/v1/audio/transcriptions` endpoint (e.g. faster-whisper-server, whisper.cpp server). This offloads inference to a dedicated GPU server.

Both providers publish transcript chunks to Redis Streams and Postgres through the same code path. The cold path still uses Whisper for full post-call re-transcription.

### 4. Insight Evaluator (Redis consumer)

Consumes transcript chunks from Redis Streams. Maintains a sliding context window per call (last ~60 seconds of transcript). On each new chunk, evaluates the window against the tenant's active real-time insight templates via LLM. Pushes detected insights to the WebSocket broadcaster and writes to Postgres.

### 5. Analysis Workers (Celery)

Post-call heavy lifting. Triggered by call-end events (Twilio `stop` message or status callback webhook). Tasks: full transcript assembly, deep multi-pass LLM analysis, summary generation, sentiment scoring, trend tagging, cost accounting. These can take 30-60 seconds — nobody's waiting in real time.

---

## Hot Path — Real-Time Pipeline

This is the hardest part of the system. The pipeline has strict latency requirements, but every component can fail independently and must degrade gracefully.

### Twilio Audio → Decoded PCM

Twilio sends audio as base64-encoded mulaw at 8kHz. The ingestion gateway decodes and resamples:

```python
import base64
import audioop
from collections import deque

class TwilioAudioHandler:
    """Handles a single Twilio Media Stream WebSocket connection."""

    def __init__(self, call_id: str, on_chunk_ready):
        self.call_id = call_id
        self.on_chunk_ready = on_chunk_ready
        self.buffer = AudioBuffer(call_id, chunk_duration_ms=500)
        self.chunk_index = 0

    async def handle_message(self, message: dict):
        event = message.get("event")

        if event == "start":
            # Extract call metadata from Twilio's start message
            start = message.get("start", {})
            self.call_sid = start.get("callSid")
            self.stream_sid = start.get("streamSid")
            self.custom_params = start.get("customParameters", {})
            # custom_params should include tenant_id passed via TwiML <Parameter>

        elif event == "media":
            media = message["media"]
            # Decode base64 mulaw payload
            mulaw_bytes = base64.b64decode(media["payload"])
            # Convert mulaw → 16-bit PCM
            pcm_8khz = audioop.ulaw2lin(mulaw_bytes, 2)
            # Resample 8kHz → 16kHz for transcription services
            pcm_16khz, _ = audioop.ratecv(pcm_8khz, 2, 1, 8000, 16000, None)

            # Buffer and emit chunks
            chunks = self.buffer.ingest(pcm_16khz)
            for chunk in chunks:
                await self.on_chunk_ready(self.call_id, chunk, self.chunk_index)
                self.chunk_index += 1

        elif event == "stop":
            # Flush remaining buffer
            if self.buffer.has_remaining():
                await self.on_chunk_ready(
                    self.call_id, self.buffer.flush(), self.chunk_index
                )
            # Trigger cold path
            await self.on_call_end(self.call_id)


class AudioBuffer:
    def __init__(self, call_id: str, chunk_duration_ms: int = 500):
        self.call_id = call_id
        self.buffer = bytearray()
        self.chunk_size = 16000 * 2 * chunk_duration_ms // 1000  # 16kHz, 16-bit
        self.chunk_index = 0

    def ingest(self, audio_bytes: bytes) -> list[bytes]:
        self.buffer.extend(audio_bytes)
        chunks = []
        while len(self.buffer) >= self.chunk_size:
            chunks.append(bytes(self.buffer[:self.chunk_size]))
            self.buffer = self.buffer[self.chunk_size:]
            self.chunk_index += 1
        return chunks

    def has_remaining(self) -> bool:
        return len(self.buffer) > 0

    def flush(self) -> bytes:
        data = bytes(self.buffer)
        self.buffer = bytearray()
        return data
```

### Transcript → Insight Evaluation

Transcript chunks land in a Redis Stream keyed by call ID. The insight evaluator runs as a consumer group — scalable horizontally, Redis guarantees each chunk is processed by exactly one consumer within the group.

The sliding window is the key design element. You don't send the entire call transcript to the LLM on every chunk — that's too slow and too expensive. Instead, maintain a window of the last ~60 seconds (~150-200 words) and evaluate just that window. The LLM prompt includes the tenant's insight templates as a structured checklist.

```python
class InsightEvaluator:
    def __init__(self, redis_client, llm_client, db_session_factory):
        self.redis = redis_client
        self.llm = llm_client
        self.db = db_session_factory
        self.windows: dict[str, SlidingWindow] = {}

    async def process_chunk(self, call_id: str, chunk: TranscriptChunk):
        # Maintain sliding window per call
        if call_id not in self.windows:
            templates = await self.load_templates(call_id)
            self.windows[call_id] = SlidingWindow(max_duration_ms=60000, templates=templates)

        window = self.windows[call_id]
        window.add(chunk)

        # Only evaluate every N chunks to control LLM costs
        if not window.should_evaluate():
            return

        # Build prompt with window context + tenant insight templates
        prompt = self.build_evaluation_prompt(window)

        # LLM call with structured output (JSON mode)
        result = await self.llm.evaluate(
            prompt=prompt,
            response_format="json",
            max_tokens=500,
            temperature=0.1  # low temp for consistent detection
        )

        # Persist + broadcast any detected insights
        for insight in result.detected_insights:
            if insight.confidence >= window.templates[insight.template_id].threshold:
                await self.persist_insight(call_id, insight)
                await self.broadcast_insight(call_id, insight)


class SlidingWindow:
    def __init__(self, max_duration_ms: int, templates: list):
        self.chunks: deque[TranscriptChunk] = deque()
        self.max_duration_ms = max_duration_ms
        self.templates = {t.id: t for t in templates}
        self.eval_counter = 0
        self.eval_interval = 3  # evaluate every 3rd chunk (~1.5s)

    def add(self, chunk: TranscriptChunk):
        self.chunks.append(chunk)
        self.eval_counter += 1
        # Evict old chunks beyond window
        while self.chunks and (
            self.chunks[-1].end_ms - self.chunks[0].start_ms > self.max_duration_ms
        ):
            self.chunks.popleft()

    def should_evaluate(self) -> bool:
        return self.eval_counter % self.eval_interval == 0

    def get_text(self) -> str:
        return " ".join(c.text for c in self.chunks)
```

**Cost control:** Evaluating every chunk is expensive. The `eval_interval` of 3 means you call the LLM roughly every 1.5 seconds. With a ~150-word window and 500 max output tokens, cost depends on the configured model (e.g. ~$0.002/evaluation on a small model like GPT-4o-mini, roughly $0.08/minute of call time). For the MVP this is fine. In production, add a smarter trigger — only evaluate when transcript content has changed meaningfully (e.g. cosine similarity against the last evaluated window drops below a threshold).

---

## Cold Path — Post-Call Analysis

When a call ends (Twilio sends `stop` on the WebSocket + a status callback webhook), a Celery task chain fires. This is where deep, expensive analysis happens — full context window, multiple LLM passes, no latency pressure.

The implemented chain:

1. **`assemble_full_transcript`** — collects hot-path transcript chunks from Postgres (Deepgram or Whisper streaming). Falls back to Whisper re-transcription of the saved WAV if no hot-path chunks exist.
2. **`run_deep_analysis`** — full-transcript LLM pass for insights the hot path may have missed (cross-conversation patterns only visible in full context). Deduplicates against hot-path insights by matching template ID + evidence text.
3. **`generate_summary`** — produces an executive summary, sentiment classification (positive/negative/neutral/mixed), key topic extraction, and structured action items with assignee and priority. Stored in the `call_summaries` table.
4. **`compute_cost_accounting`** — tallies total input/output tokens consumed across all LLM calls in the chain, stores in the summary's `token_cost` field and the call's metadata, marks the call as `completed`.

```python
from celery import chain

def on_call_end(call_id: str):
    pipeline = chain(
        assemble_full_transcript.s(call_id),
        run_deep_analysis.s(),       # full-transcript LLM pass for insights hot path may have missed
        generate_summary.s(),         # executive summary, sentiment, key topics
        extract_action_items.s(),     # commitments, follow-ups, escalations
        compute_cost_accounting.s(),  # total tokens, cost per provider, per tenant
        update_trend_aggregates.s(),  # roll up into tenant-level analytics
    )
    pipeline.apply_async()


@celery_app.task(bind=True, max_retries=3)
def run_deep_analysis(self, transcript_data: dict):
    """Second-pass insight detection with full call context.

    The hot path evaluates 60-second windows — it can miss insights
    that only become apparent in full context. E.g., "the caller
    mentioned budget concerns in minute 2 and asked about cancellation
    in minute 8 — together these indicate churn risk."
    """
    call_id = transcript_data["call_id"]
    full_text = transcript_data["full_transcript"]

    templates = InsightTemplate.query.filter_by(
        tenant_id=transcript_data["tenant_id"],
        active=True
    ).all()

    # Use a more capable model for deep analysis (vs. small model on hot path)
    result = llm_client.analyze(
        model=Config.LLM_MODEL,  # configurable via LLM_MODEL env var
        prompt=build_deep_analysis_prompt(full_text, templates),
        max_tokens=2000,
        temperature=0.2
    )

    # Deduplicate against real-time insights already detected
    existing = Insight.query.filter_by(call_id=call_id).all()
    new_insights = deduplicate(result.insights, existing)

    for insight in new_insights:
        db.session.add(Insight(
            call_id=call_id,
            template_id=insight.template_id,
            source="post_call",
            confidence=insight.confidence,
            evidence=insight.evidence,
            result=insight.structured_data,
        ))
    db.session.commit()

    return {**transcript_data, "deep_insights_count": len(new_insights)}
```

---

## Integration Layer — Audio Ingestion

### Twilio Media Streams (Primary)

The ingestion gateway runs a WebSocket server that Twilio connects to when a call starts. The TwiML configuration on the Twilio phone number controls when and how streaming is initiated.

Example TwiML (returned by your Flask API when Twilio makes a webhook request for an incoming call):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="wss://your-domain.com/ws/twilio/stream">
            <Parameter name="tenant_id" value="uuid-of-tenant"/>
        </Stream>
    </Start>
    <Dial>+15551234567</Dial>
</Response>
```

This tells Twilio to:
1. Fork the audio and stream it to your WebSocket endpoint
2. Pass the `tenant_id` as a custom parameter (available in the `start` WebSocket message)
3. Connect the call to the destination number
4. Streaming continues for the entire duration of the call

The Flask API serves the TwiML webhook:

```python
@app.route("/webhooks/twilio/voice", methods=["POST"])
def twilio_voice_webhook():
    """Twilio requests this when a call comes in to your number."""
    call_sid = request.form.get("CallSid")
    from_number = request.form.get("From")
    to_number = request.form.get("To")

    # Look up which tenant owns this Twilio number
    tenant = Tenant.query.filter(
        Tenant.settings["twilio_numbers"].contains([to_number])
    ).first()

    if not tenant:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Error</Say></Response>',
            content_type="text/xml"
        )

    # Return TwiML that starts the media stream with tenant context
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Start>
            <Stream url="wss://{INGESTION_HOST}/ws/twilio/stream">
                <Parameter name="tenant_id" value="{tenant.id}"/>
            </Stream>
        </Start>
        <Dial>{request.form.get("ForwardTo", "+15551234567")}</Dial>
    </Response>"""

    return Response(twiml, content_type="text/xml")
```

### Provider Adapter Interface (for future providers)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class AudioSource(ABC):
    @abstractmethod
    async def get_audio_stream(self, call_id: str) -> AsyncIterator[bytes]:
        """Yield audio chunks. For Twilio: decoded from WebSocket. For SIP: from RTP."""

    @abstractmethod
    def get_call_metadata(self, call_id: str) -> dict:
        """Return caller, callee, direction, timestamps, etc."""
```

### Development Setup with ngrok

During development, Twilio needs to reach your local WebSocket server. Use ngrok:

```bash
# Terminal 1: Start the ingestion gateway
python -m callisto.ingestion.server  # listens on ws://localhost:8765

# Terminal 2: Expose via ngrok
ngrok http 8765  # gives you a wss://xxx.ngrok.io URL

# Configure your Twilio number's voice webhook to point to your Flask API
# Configure the TwiML stream URL to use the ngrok WSS URL
```

---

## API Surface

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/auth/google/login` | Redirect to Google OAuth consent screen |
| `GET` | `/auth/google/callback` | Handle OAuth callback, issue JWT |
| `GET` | `/auth/me` | Return current user + tenant from JWT |
| `POST` | `/api/v1/tenants` | Register new tenant, returns API key |
| `PUT` | `/api/v1/tenants/:id` | Update tenant settings |
| `CRUD` | `/api/v1/templates` | Manage insight templates (what to look for) |
| `CRUD` | `/api/v1/contacts` | Manage contacts (name, company, phone numbers, email) |
| `POST` | `/api/v1/contacts/import` | CSV import with column mappings, upsert on phone |
| `POST` | `/api/v1/contacts/sync/google` | Sync contacts from Google People API |
| `GET` | `/api/v1/calls` | List calls with filters, includes contact name/company |
| `GET` | `/api/v1/calls/:id` | Full call detail: transcript, insights, summary |
| `GET` | `/api/v1/calls/:id/insights` | Insights for a call with evidence + confidence |
| `GET` | `/api/v1/calls/:id/transcript` | Full transcript with speaker labels and timestamps |
| `GET` | `/api/v1/calls/:id/summary` | Post-call summary, sentiment, topics, action items |
| `GET` | `/api/v1/analytics/trends` | Aggregated insight trends over time per template |
| `WS` | `/ws/calls/:id/live` | Real-time insight stream during active call |
| `WS` | `/ws/calls/live` | Real-time insight stream for all calls |
| `POST` | `/webhooks/twilio/voice` | Twilio voice webhook — returns TwiML with stream config |
| `POST` | `/webhooks/twilio/status` | Twilio call status callback (call ended, etc.) |
| `WSS` | `/ws/twilio/stream` | Twilio Media Streams WebSocket endpoint (ingestion) |

---

## Infrastructure

### Development (Docker Compose)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: callisto
      POSTGRES_PASSWORD: dev
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: .
    command: flask run --host=0.0.0.0
    environment:
      DATABASE_URL: postgresql://postgres:dev@postgres/callisto
      REDIS_URL: redis://redis:6379/0
      TWILIO_ACCOUNT_SID: ${TWILIO_ACCOUNT_SID}
      TWILIO_AUTH_TOKEN: ${TWILIO_AUTH_TOKEN}
      DEEPGRAM_API_KEY: ${DEEPGRAM_API_KEY}
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.openai.com/v1}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o-mini}
    ports: ["5000:5000"]
    depends_on: [postgres, redis]

  ingestion:
    build: .
    command: python -m callisto.ingestion.server
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://postgres:dev@postgres/callisto
      DEEPGRAM_API_KEY: ${DEEPGRAM_API_KEY}
    ports: ["8765:8765"]  # WebSocket for Twilio Media Streams
    depends_on: [redis, postgres]

  evaluator:
    build: .
    command: python -m callisto.evaluator.consumer
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://postgres:dev@postgres/callisto
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.openai.com/v1}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o-mini}
    depends_on: [redis, postgres]
    deploy:
      replicas: 2  # scale based on concurrent call volume

  worker:
    build: .
    command: celery -A callisto.tasks worker -l info -c 4
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://postgres:dev@postgres/callisto
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.openai.com/v1}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o-mini}
    depends_on: [redis, postgres]

volumes:
  pgdata:
```

### Production Path

Each service becomes a K8s Deployment. Evaluator and worker scale on queue depth (KEDA). Postgres moves to RDS. Redis moves to ElastiCache. Terraform manages all of it. Ingestion gateway needs sticky sessions (one WebSocket per call), so it gets a StatefulSet or a session-aware load balancer.

---

## Legal & Compliance

Build consent tracking into the data model from day one — it's table stakes, not a feature.

- The `consent_given` flag on the Call model gates whether audio is processed at all
- The API should reject insight queries for calls where consent wasn't recorded
- Two-party consent states (California, Florida, Illinois, and others) require all parties to be notified
- The platform should make it easy for tenants to configure consent workflows — automated disclosure playback before monitoring begins, consent logging with timestamps
- Audio retention policies should be configurable per tenant — auto-delete audio after N days while retaining transcripts and insights
- The transcript and insight data is the product; the raw audio is a liability
- Twilio provides `<Say>` TwiML for automated consent disclosure before streaming begins

---

## MVP Phases

### Phase 1 — Live Audio Pipeline (Week 1-2)

**Goal:** End-to-end pipeline from a live phone call to insights in the database.

- Flask API with tenant + insight template CRUD
- SQLAlchemy models + Alembic migrations
- Twilio webhook endpoint returning TwiML with `<Start><Stream>`
- Ingestion gateway: WebSocket server accepting Twilio Media Streams
- Audio decoding: base64 mulaw → PCM, 8kHz → 16kHz resampling
- Deepgram streaming transcription integration
- Transcript chunks published to Redis Streams
- Single-pass insight evaluation (evaluate full accumulated transcript periodically, not yet sliding window)
- Store transcript chunks and insights in Postgres
- Call detail + insights viewable via API
- ngrok for local development with Twilio

**Demo:** Call your Twilio number → speak → see transcript and detected insights in the database via API.

### Phase 2 — Real-Time Insight Loop (Week 3-4)

- Sliding window insight evaluator consuming Redis Streams
- Per-window LLM evaluation with structured output (JSON mode)
- WebSocket broadcaster for live insight delivery to agent dashboards
- Simple web dashboard showing insights appearing during a live call
- Twilio status callback webhook for call lifecycle events
- **This is the "wow" demo moment**

### Phase 3 — Cold Path + Deep Analysis (Week 5-6)

- Celery post-call analysis chain (full transcript re-analysis, summary, action items, sentiment)
- Insight deduplication between real-time and post-call passes
- Cost accounting (tokens consumed per call, per tenant)
- Call summary and trend aggregation
- Analytics endpoints

### Phase 4 — Auth, Multi-Tenant Hardening + React Frontend (Week 7-8)

**Backend:**
- Multi-tenant API key auth with rate limiting
- Per-tenant Twilio number configuration via API
- Google OAuth login endpoints (`/auth/google/login`, `/auth/google/callback`)
- JWT session management — Google accounts tied to tenants
- Trend aggregation and analytics endpoints

**Frontend (React + Vite, lives in `frontend/` at repo root):**
- Login page with Google OAuth
- Dashboard: active and recent calls with real-time insight updates via WebSocket
- Call detail view: full transcript, detected insights with confidence scores and evidence highlights, post-call summary with sentiment/topics/action items
- Insight templates management: CRUD, toggle active/inactive, category and severity
- Analytics page: insight trends over time per template

**Demo:** Log in with Google → see your tenant's calls appearing in real time → click into a call to see transcript + insights streaming live → review post-call summary → manage what insights to look for → view trends across all calls.

---

## Cost Considerations

### Development Costs

- **Telephony:** Twilio free trial includes a phone number and trial credits. After trial, DIDs are ~$1/month, calls are ~$0.0085/min inbound. Media Streams add $0.004/min.
- **Transcription (streaming):** Deepgram free tier provides $200 credit (~775 hours of Nova-2 at $0.0043/min), no expiration
- **LLM:** Any OpenAI-compatible endpoint. Default GPT-4o-mini for hot path (~$0.08/min of call time), larger model configurable for cold path deep analysis. Works with OpenAI, Anthropic (via proxy), Ollama (local/free), Together, OpenRouter, vLLM, etc.
- **Infrastructure:** Postgres + Redis run locally via Docker. No cloud services needed until production.

### Production Cost Profile

Per minute of call processed:
- Twilio (inbound + media stream): ~$0.013
- Transcription: ~$0.01-0.02 (Deepgram) or $0 (self-hosted Whisper with GPU)
- Hot path LLM (e.g. GPT-4o-mini): ~$0.08
- Cold path LLM (e.g. GPT-4o): ~$0.02-0.05 per call (one-time, not per-minute)
- Infrastructure: negligible at low volume

Total: roughly $0.12-0.17 per minute of call at scale. This sets a floor for pricing.

---

## Competitive Landscape

- **Gong / Chorus (ZoomInfo):** Enterprise sales intelligence. Expensive ($100+/user/month), locked to sales use cases, no configurable insight templates. They analyze what THEY think matters, not what the customer defines.
- **CallRail:** Call tracking and analytics for marketing. Focused on attribution, not real-time insight detection.
- **Observe.AI / Balto:** Contact center QA tools. Closer competitors but focused on agent coaching, not configurable business intelligence.

**Differentiation:** "Bring your own insight criteria" — the tenant defines what to look for, not the platform. This makes it horizontal across sales, support, compliance, healthcare, legal, finance. The configurable template system is the moat.
