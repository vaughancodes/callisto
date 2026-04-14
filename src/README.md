# Callisto Backend

Python backend for the Callisto telephony intelligence platform. Built with Flask, SQLAlchemy, Celery, and async WebSocket servers.

## Package Structure

```
src/callisto/
├── app.py                   # Flask app factory + Celery factory
├── config.py                # All configuration from environment variables
├── extensions.py            # SQLAlchemy db instance
├── celery_app.py            # Celery app initialization
├── tasks.py                 # Cold-path Celery task chain
├── twilio_client.py         # Twilio REST wrapper (numbers, SIP Domains, credentials, outbound calls)
│
├── models/                  # SQLAlchemy models
│   ├── organization.py      # Organization + OrganizationMembership (top of role hierarchy)
│   ├── tenant.py            # Tenant (FK to organization, SIP Domain SID + credential list SID)
│   ├── phone_number.py      # PhoneNumber: org+tenant FK, twilio_sid, inbound/outbound flags, SIP user, inbound_mode
│   ├── membership.py        # TenantMembership (user ↔ tenant, is_admin)
│   ├── user.py              # Google OAuth users (google_id, email, tenant FK, is_superadmin)
│   ├── contact.py           # Contacts (name, company, phone_numbers JSONB, Google sync, notes)
│   ├── call.py              # Call records + CallSummary (sentiment, topics, action items)
│   ├── transcript.py        # Transcript chunks (speaker, text, timestamps, confidence)
│   └── insight.py           # InsightTemplate (inbound_enabled/outbound_enabled flags) + Insight
│
├── api/                     # REST API (Flask Blueprint, JWT-protected)
│   ├── __init__.py          # Blueprint + before_request JWT middleware
│   ├── tenants.py           # Tenant CRUD
│   ├── tenant_settings.py   # Tenant admin: settings, members, phone number routing, SIP user mint/revoke
│   ├── organizations.py     # Org admin: org details, tenants in org, number pool → tenant assignment, org admins
│   ├── calls.py             # Call list/detail (with other_party_number + friendly_name), transcript, insights, summary, notes, outbound initiation
│   ├── contacts.py          # Contact CRUD, CSV import, phone lookup, backfill, dedup conflict detection
│   ├── templates.py         # Insight template CRUD with inbound/outbound direction flags
│   ├── analytics.py         # Insight trends over time
│   ├── admin.py             # Superadmin: organization CRUD, Twilio number pool → org assignment, user management, cascade_delete_tenant helper
│   ├── google_sync.py       # Google Contacts sync via People API
│   └── webhooks.py          # Twilio voice webhook: handles inbound, REST-API outbound, and SIP-originated calls
│
├── auth/                    # Authentication
│   ├── routes.py            # Google OAuth flow (/auth/google/login, /callback, /me, /switch-tenant)
│   └── middleware.py        # JWT verify + require_superadmin / require_org_admin / require_tenant_admin (org-aware)
│
├── ingestion/               # Twilio Media Streams (async WebSocket server)
│   ├── server.py            # Two-track audio handler, direction-aware contact lookup, STT, publish to Redis
│   ├── audio.py             # mulaw decode, 8kHz→16kHz resample, AudioBuffer
│   └── __main__.py          # python -m callisto.ingestion.server
│
├── transcription/           # Speech-to-text providers
│   ├── deepgram.py          # Streaming WebSocket client for Deepgram Nova-2 (one stream per track)
│   └── whisper.py           # Local openai-whisper or remote API (per-track buffers)
│
├── evaluation/              # Real-time insight detection (async Redis consumer)
│   ├── consumer.py          # InsightEvaluator: Redis Streams → direction-filtered templates → LLM → Postgres + Pub/Sub
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

All tables use UUID primary keys. The role hierarchy goes Organization → Tenant → user, with column-based isolation at every level (`organization_id` and/or `tenant_id` on every domain table).

- **Organization** — top of the hierarchy (name, slug, description). Owns a pool of phone numbers and one or more tenants.
- **OrganizationMembership** — user ↔ organization with `is_admin` flag. Org admins implicitly have tenant-admin powers on every tenant in their org.
- **Tenant** — belongs to an Organization. Holds business context, the lazy-created Twilio SIP Domain SID + credential list SID, and tenant-scoped settings.
- **TenantMembership** — user ↔ tenant with `is_admin` flag. Direct tenant members.
- **PhoneNumber** — Twilio number assigned to an organization (`organization_id`) and optionally to a tenant within that org (`tenant_id`). Carries `inbound_enabled`, `outbound_enabled`, `inbound_mode` (`none`/`sip`/`forward`), `inbound_forward_to`, `sip_username`, `sip_credential_sid`, `friendly_name`, and the Twilio `twilio_sid`.
- **User** — Google OAuth (google_id, email), `is_superadmin` flag, optional active `tenant_id`.
- **Contact** — name, company, phone_numbers (JSONB array of E.164), email, Google sync ID, notes. Phone numbers are unique per tenant.
- **Call** — Twilio Call SID, contact FK, direction (`inbound` / `outbound`), status, timestamps, duration, notes, caller_number, callee_number.
- **CallSummary** — summary text, sentiment, key_topics, action_items, LLM model, token cost.
- **Transcript** — per-chunk: speaker (`external` / `internal`), text, start/end ms, confidence, chunk_index.
- **InsightTemplate** — configurable: name, LLM prompt, category, severity, is_realtime, `inbound_enabled`, `outbound_enabled`. The evaluator and cold-path filter templates by direction at evaluation time.
- **Insight** — detection: template FK, source (realtime/post_call), confidence, evidence, reasoning.

## STT Providers

Configured via `STT_PROVIDER` env var:

| Provider | Value | Description |
|----------|-------|-------------|
| Auto | `auto` | Uses Deepgram if key is set, otherwise Whisper |
| Deepgram | `deepgram` | Streaming WebSocket to Deepgram Nova-2 (~300ms latency) |
| Whisper | `whisper` | Batched segments (local `openai-whisper` or remote API via `WHISPER_API_URL`) |

Falls back automatically: if Deepgram connection fails at call start, switches to Whisper for that call.

## API Endpoints

### Auth
- `GET /auth/google/login` — redirect to Google OAuth
- `GET /auth/google/callback` — handle callback, issue JWT
- `GET /auth/me` — current user, active tenant, tenant + organization memberships, effective role flags
- `POST /auth/switch-tenant` — switch the active tenant (any tenant the user can reach via direct or org membership)

### API (JWT-protected, `/api/v1/`)

**Tenant settings + members**
- `GET/PUT /tenants/:id/settings` — tenant context (read by all members; only context is editable; name/description are managed at the org level)
- `GET /tenants/:id/members`, `POST /tenants/:id/members`, `PUT /tenants/:id/members/:user_id`, `DELETE .../members/:user_id`
- `GET /tenants/:id/numbers`, `PUT /tenants/:id/numbers/:num_id` (friendly name, inbound/outbound flags, inbound mode, forward target)
- `POST /tenants/:id/numbers/:num_id/sip-user` — mint a SIP credential (returns the password ONCE)
- `DELETE /tenants/:id/numbers/:num_id/sip-user` — revoke the SIP credential

**Organizations (org admin)**
- `GET/PUT /organizations/:id` — org details (description editable; name read-only here, managed by superadmin)
- `GET/POST /organizations/:id/tenants`, `PUT/DELETE /organizations/:id/tenants/:tenant_id` (slug auto-tracks name)
- `GET /organizations/:id/numbers`, `PUT /organizations/:id/numbers/:num_id` (assign/unassign to tenant — revokes SIP creds and resets routing flags on transition)
- `GET/POST /organizations/:id/admins`, `DELETE .../admins/:user_id`

**Calls**
- `GET /tenants/:id/calls` — list with `direction`, `other_party_number`, `our_number_friendly_name`, summary preview
- `POST /tenants/:id/calls/outbound` — initiate an outbound call via Twilio REST API
- `GET /calls/:id`, `GET /calls/:id/transcript`, `GET /calls/:id/insights`, `GET /calls/:id/summary`, `PUT /calls/:id/notes`

**Contacts**
- `GET/POST /tenants/:id/contacts`, `GET/PUT/DELETE /contacts/:id`, `PUT /contacts/:id/notes`
- `POST /tenants/:id/contacts/import` (CSV), `POST /tenants/:id/contacts/backfill`, `POST /contacts/sync/google`

**Templates**
- `GET/POST /tenants/:id/templates` — CRUD with `inbound_enabled` / `outbound_enabled` flags
- `PUT/DELETE /templates/:id`

**Analytics**
- `GET /tenants/:id/analytics/insights` — insight trends over time

### Admin (superadmin only, `/api/admin/`)
- `GET/POST/PUT/DELETE /organizations` — organization CRUD (name change auto-regenerates slug)
- `GET /organizations/:id/numbers`, `POST /organizations/:id/numbers` (assign by Twilio SID — also wires the voice webhook), `DELETE /organizations/:id/numbers/:num_id` (revokes SIP creds + clears webhook)
- `GET/POST /organizations/:id/admins`, `DELETE .../admins/:user_id`
- `GET /twilio/numbers` — list every IncomingPhoneNumber on the Twilio account joined with our DB state
- `GET/POST /tenants`, `PUT/DELETE /tenants/:id` — tenant CRUD (UI now manages tenants from Org Settings)
- `GET /users`, `PUT/DELETE /users/:id`

### Webhooks (unprotected)
- `POST /webhooks/twilio/voice` — single endpoint handling three modes:
  - **Inbound** PSTN call → look up tenant by `To`, route per `inbound_mode` (record-only / `<Dial><Sip>` to ring SIP device / `<Dial>` to forward)
  - **REST-API outbound** → look up tenant by `From`, return `<Pause>` while the stream captures audio
  - **SIP-originated outbound** (when `?tenant_id=` is on the URL and `From` is a SIP URI) → look up tenant + phone number from the SIP user, return `<Dial callerId="..."><Number>...</Number></Dial>` with the dialed destination
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
