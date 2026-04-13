# Callisto Backend

Python backend for the Callisto telephony intelligence platform. Built with Flask, SQLAlchemy, Celery, and async WebSocket servers.

## Package Structure

```
src/callisto/
├── app.py                  # Flask app factory + Celery factory
├── config.py               # All configuration from environment variables
├── extensions.py            # SQLAlchemy db instance
├── celery_app.py            # Celery app initialization
├── tasks.py                 # Cold-path Celery task chain
│
├── models/                  # SQLAlchemy models
│   ├── tenant.py            # Multi-tenant root (name, slug, settings, API key)
│   ├── user.py              # Google OAuth users (google_id, email, tenant FK, is_superadmin)
│   ├── contact.py           # Contacts (name, company, phone_numbers JSONB, Google sync)
│   ├── call.py              # Call records + CallSummary (sentiment, topics, action items)
│   ├── transcript.py        # Transcript chunks (speaker, text, timestamps, confidence)
│   └── insight.py           # InsightTemplate (configurable detection) + Insight (detections)
│
├── api/                     # REST API (Flask Blueprint, JWT-protected)
│   ├── __init__.py          # Blueprint + before_request JWT middleware
│   ├── tenants.py           # Tenant CRUD
│   ├── calls.py             # Call list/detail, transcript, insights, summary, notes
│   ├── contacts.py          # Contact CRUD, CSV import, phone lookup, backfill
│   ├── templates.py         # Insight template CRUD
│   ├── analytics.py         # Insight trends over time
│   ├── admin.py             # Superadmin: tenant/user management
│   ├── google_sync.py       # Google Contacts sync via People API
│   └── webhooks.py          # Twilio voice webhook (TwiML) + status callback
│
├── auth/                    # Authentication
│   ├── routes.py            # Google OAuth flow (/auth/google/login, /callback, /me)
│   └── middleware.py        # JWT verification + superadmin check
│
├── ingestion/               # Twilio Media Streams (async WebSocket server)
│   ├── server.py            # Main handler: decode audio, STT, publish to Redis
│   ├── audio.py             # mulaw decode, 8kHz→16kHz resample, AudioBuffer
│   └── __main__.py          # python -m callisto.ingestion.server
│
├── transcription/           # Speech-to-text providers
│   ├── deepgram.py          # Streaming WebSocket client for Deepgram Nova-2
│   └── whisper.py           # Local openai-whisper or remote API
│
├── evaluation/              # Real-time insight detection (async Redis consumer)
│   ├── consumer.py          # InsightEvaluator: Redis Streams → LLM → Postgres + Pub/Sub
│   ├── window.py            # SlidingWindow + TranscriptChunk dataclass
│   └── __main__.py          # python -m callisto.evaluator.consumer
│
└── broadcaster/             # Real-time WebSocket broadcaster
    ├── server.py            # Redis Pub/Sub → WebSocket clients
    └── __main__.py          # python -m callisto.broadcaster.server
```

## Services

The backend runs as 5 separate processes:

### API (`flask` / `gunicorn`)
REST API + Twilio webhooks + Google OAuth. Runs Alembic migrations on startup.

```bash
gunicorn -b 0.0.0.0:5309 'callisto.app:create_app()' --reload
```

### Ingestion Server (`websockets`)
Accepts Twilio Media Streams WebSocket connections. Decodes mulaw audio, resamples to 16kHz, forwards to Deepgram or batches for Whisper, publishes transcript chunks to Redis Streams, persists to Postgres, saves WAV for cold-path.

```bash
python -m callisto.ingestion.server
```

### Evaluator (`asyncio` + `redis`)
Consumes transcript chunks from Redis Streams. Maintains a 60-second sliding window per call. Evaluates every utterance against the tenant's active insight templates via LLM. Deduplicates by evidence overlap. Persists to Postgres and broadcasts via Redis Pub/Sub.

```bash
python -m callisto.evaluator.consumer
```

### Broadcaster (`websockets`)
Subscribes to Redis Pub/Sub `insights:*` channels. Forwards to connected WebSocket clients watching specific calls or all calls.

```bash
python -m callisto.broadcaster.server
```

### Celery Worker
Cold-path processing chain triggered when a call ends:
1. `assemble_full_transcript` — collect hot-path chunks or Whisper fallback
2. `run_deep_analysis` — full-context LLM pass, deduped against hot-path
3. `generate_summary` — sentiment, key topics, action items
4. `compute_cost_accounting` — tally tokens, mark call completed

```bash
celery -A callisto.celery_app worker -l info -c 4
```

## Data Models

All tables use UUID primary keys and column-based multi-tenancy (`tenant_id` on every table).

- **Tenant** — name, slug, settings (JSONB for Twilio numbers, STT prefs, etc.)
- **User** — Google OAuth (google_id, email), linked to tenant, `is_superadmin` flag
- **Contact** — name, company, phone_numbers (JSONB array of E.164), email, Google sync ID, notes
- **Call** — Twilio Call SID, contact FK, direction, status, timestamps, duration, notes
- **CallSummary** — summary text, sentiment, key_topics, action_items, LLM model, token cost
- **Transcript** — per-chunk: speaker, text, start/end ms, confidence, chunk_index
- **InsightTemplate** — configurable: name, LLM prompt, category, severity, is_realtime
- **Insight** — detection: template FK, source (realtime/post_call), confidence, evidence, reasoning

## STT Providers

Configured via `STT_PROVIDER` env var:

| Provider | Value | Description |
|----------|-------|-------------|
| Auto | `auto` | Uses Deepgram if key is set, otherwise Whisper |
| Deepgram | `deepgram` | Streaming WebSocket to Deepgram Nova-2 (~300ms latency) |
| Whisper | `whisper` | Batched segments (local `openai-whisper` or remote API via `WHISPER_API_URL`) |

Falls back automatically: if Deepgram connection fails at call start, switches to Whisper for that call.

## API Endpoints

### Auth (unprotected)
- `GET /auth/google/login` — redirect to Google OAuth
- `GET /auth/google/callback` — handle callback, issue JWT
- `GET /auth/me` — current user + tenant from JWT

### API (JWT-protected, `/api/v1/`)
- `GET/POST /tenants/:id/calls` — list/query calls
- `GET /calls/:id` — call detail
- `GET /calls/:id/transcript` — transcript chunks
- `GET /calls/:id/insights` — detected insights
- `GET /calls/:id/summary` — post-call summary
- `PUT /calls/:id/notes` — update call notes
- `GET/POST /tenants/:id/contacts` — list/create contacts
- `GET/PUT/DELETE /contacts/:id` — contact CRUD
- `PUT /contacts/:id/notes` — update contact notes
- `POST /tenants/:id/contacts/import` — CSV import
- `POST /tenants/:id/contacts/backfill` — match calls to contacts
- `POST /contacts/sync/google` — Google Contacts sync
- `GET/POST /tenants/:id/templates` — insight template CRUD
- `PUT/DELETE /templates/:id` — update/delete template
- `GET /tenants/:id/analytics/insights` — insight trends

### Admin (superadmin only, `/api/admin/`)
- `GET/POST /tenants` — list/create tenants
- `PUT/DELETE /tenants/:id` — update/delete tenant
- `GET /users` — list users
- `PUT/DELETE /users/:id` — update/delete user

### Webhooks (unprotected)
- `POST /webhooks/twilio/voice` — returns TwiML with `<Start><Stream>`
- `POST /webhooks/twilio/status` — call status callback

### WebSocket
- `WSS /ws/twilio/stream` — Twilio Media Streams (ingestion)
- `WSS /ws/calls/:id/live` — real-time insights for a call
- `WSS /ws/calls/live` — real-time insights for all calls

## Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

Migrations run automatically on API container startup.
