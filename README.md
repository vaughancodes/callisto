<p align="center">
  <img src="frontend/public/callisto-icon-animated.svg" alt="" height="120" align="middle">
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="frontend/public/callisto-wordmark-dark.svg" alt="Callisto" height="100" align="middle">
</p>

<p align="center">
  <strong>Telephony intelligence for organizations and their teams</strong><br>
  Real-time call analysis with configurable LLM-powered insight detection.
</p>

---

Callisto listens to live phone calls via Twilio Media Streams, transcribes audio in real time with Deepgram or Whisper, and evaluates configurable insight templates against the conversation using any OpenAI-compatible LLM. Detected insights are delivered to dashboards over WebSocket as the call happens, with deep post-call analysis, summaries, and trend analytics.

A multi-tier hierarchy lets multiple teams share infrastructure cleanly: superadmins manage **organizations** and assign them Twilio numbers from the account pool; org admins assign numbers to **tenants** within their org and manage tenant lifecycle; tenant admins configure per-number routing (inbound, outbound, or both), mint **SIP credentials** for desk/softphones, and curate insight templates and contacts.

## Architecture

```
Twilio Call ──► Ingestion Server (WebSocket, port 5310)
                  │
                  ├─► Deepgram Streaming / Whisper ──► Redis Streams
                  │                                        │
                  │                                   Evaluator (Redis consumer)
                  │                                        │
                  │                                   LLM evaluation (sliding window)
                  │                                        │
                  │                                   Redis Pub/Sub ──► Broadcaster (WS, port 5311)
                  │                                        │                    │
                  │                                   Postgres              React Frontend
                  │
                  └─► WAV file ──► Celery cold-path chain
                                      ├─► Deep analysis (full-transcript LLM pass)
                                      ├─► Summary generation (sentiment, topics, action items)
                                      └─► Cost accounting
```

**Services:**

| Service | Port | Description |
|---------|------|-------------|
| `api` | 5309 | Flask REST API + Twilio webhooks + Google OAuth + Twilio SIP/number management |
| `ingestion` | 5310 | WebSocket server for Twilio Media Streams (handles inbound, REST-API outbound, and SIP-originated calls) |
| `evaluator` | — | Redis Streams consumer, sliding window LLM evaluation, direction-aware template filtering |
| `broadcaster` | 5311 | WebSocket server for real-time insight delivery |
| `worker` | — | Celery worker for cold-path analysis |
| `frontend` | 5308 | React + Vite dashboard (`app.yourdomain.com`) |
| `marketing` | 5307 | React + Vite marketing site (`yourdomain.com`) |
| `postgres` | 5433 | PostgreSQL 16 |
| `redis` | 6380 | Redis 7 (Celery broker + Redis Streams + Pub/Sub) |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A Twilio account with a phone number
- A Deepgram account (free tier: $200 credit) or local Whisper
- An OpenAI-compatible LLM endpoint (OpenAI, Ollama, etc.)
- A Google Cloud project with OAuth credentials

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

Generate a JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Start all services

```bash
docker compose up --build
```

This starts all 8 services. The API runs migrations automatically on startup.

### 3. Set up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Add your redirect URI: `https://your-domain.com/auth/google/callback`
4. Enable the **People API** (for Google Contacts sync)
5. Add your email as a test user in the OAuth consent screen

### 4. Configure Twilio

Set your Twilio phone number's voice webhook to:

```
POST https://your-domain.com/webhooks/twilio/voice
```

### 5. Configure nginx (or your choice of reverse proxy)

Callisto needs a reverse proxy to route traffic to the correct services.
The following is an example of an nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name app.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/app.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.yourdomain.com/privkey.pem;

    # Flask API
    location /api/ {
        proxy_pass http://127.0.0.1:5309;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API-side auth endpoints. /auth/callback is intentionally excluded so it
    # falls through to the frontend (it's a React Router page, not a Flask route).
    location ~ ^/auth/(google|me|switch-tenant) {
        proxy_pass http://127.0.0.1:5309;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhooks/ {
        proxy_pass http://127.0.0.1:5309;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /health {
        proxy_pass http://127.0.0.1:5309;
    }

    # Twilio Media Streams WebSocket
    location /ws/twilio/ {
        proxy_pass http://127.0.0.1:5310;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Broadcaster WebSocket
    location /ws/calls/ {
        proxy_pass http://127.0.0.1:5311;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Frontend (everything else, including /auth/callback)
    location / {
        proxy_pass http://127.0.0.1:5308;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 6. Create an organization, then a tenant

Log in via Google OAuth at `https://app.yourdomain.com`. If your email is in `SUPERADMIN_EMAILS`, you'll have superadmin access.

1. **Administration** (superadmin only) — create a new **organization**, then assign Twilio numbers from your Twilio account to that organization. The Phone Numbers table is populated live from the Twilio API and any reassignment automatically updates each number's voice webhook on Twilio.
2. **Organization Settings** (org admin) — create one or more **tenants** under the org and assign numbers from the org's pool to specific tenants. Org admins also manage org membership.
3. **Tenant Settings** (tenant admin) — for each assigned number, click **Edit Configuration** to set a friendly name, enable inbound and/or outbound, choose how inbound calls route (record-only, ring a SIP device, or forward to another number), and optionally mint a SIP user so a deskphone or softphone can register against the number directly.

### 7. (Optional) Mint SIP credentials for an external phone

In **Tenant Settings → Phone Numbers → Edit Configuration**, click **Create SIP User** to generate username/password credentials for the number. Callisto will lazily create a Twilio SIP Domain for the tenant on first use, configure it for both call and registration auth, and surface the credentials once in a reveal modal (the password is shown only on creation — Twilio never returns it again). Drop those credentials into Linphone, Zoiper, Bria, or any SIP-capable deskphone (Polycom/Yealink/Cisco) and the device can place outbound calls and receive inbound calls through Callisto.

### 8. Add insight templates

Go to Templates and create templates that define what Callisto should look
for in calls. Each template is a natural-language rule the LLM evaluates
against the transcript. Each template can be limited to **inbound calls**,
**outbound calls**, or both — the evaluator and cold-path filter by call
direction so an inbound-only template never fires on an outbound call.

Some **example** templates to get you started:

| Name | Category | Severity | Prompt |
|------|----------|----------|--------|
| Follow-up Request | custom | info | Detect if the external party asks for a callback or requests that someone follow up with them. |
| Pricing Question | custom | info | Detect if the external party asks about pricing, cost, fees, or billing. |
| Topic Mention | custom | info | Detect if the external party brings up a specific topic relevant to your business. |

These are just examples — define whatever makes sense for your own use case.

### 9. Make a call

Either call your Twilio number from any phone (inbound), or place a call from a registered SIP device (outbound). The call appears in the dashboard's recent calls list with an incoming/outgoing arrow icon, the friendly name of the number it ran on, and live insights stream into the right-hand panel as the conversation unfolds. When the call ends, a Celery cold-path runs deep analysis, generates a summary, and tags topics, sentiment, and action items.

## Environment Variables

See [`.env.example`](.env.example) for the complete list with descriptions.

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_API_KEY` | Yes | API key for your LLM provider |
| `LLM_BASE_URL` | Yes | OpenAI-compatible endpoint URL |
| `LLM_MODEL` | Yes | Model name (e.g. `gpt-4o-mini`, `llama3.2`) |
| `DEEPGRAM_API_KEY` | No | Enables Deepgram streaming STT |
| `STT_PROVIDER` | No | `auto`, `deepgram`, or `whisper` |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio auth token |
| `PUBLIC_BASE_URL` | Yes | Canonical public URL of the deployment, e.g. `https://app.yourdomain.com`. Used to build the Twilio voice webhook URL, the Media Stream WebSocket URL embedded in TwiML, and the SIP Domain voice webhook |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Yes | OAuth callback URL |
| `JWT_SECRET` | Yes | Secret for signing JWTs |
| `SUPERADMIN_EMAILS` | No | Comma-separated emails that get superadmin on first login |
| `FRONTEND_URL` | Yes | Frontend URL for OAuth redirects |

## Project Structure

```
callisto/
├── src/callisto/              # Python backend
│   ├── app.py                 # Flask app factory
│   ├── config.py              # Configuration from env vars
│   ├── twilio_client.py       # Twilio REST wrapper (numbers, SIP Domains, credentials)
│   ├── models/                # SQLAlchemy models (Organization, Tenant, PhoneNumber, Call, Contact, Insight, ...)
│   ├── api/                   # REST API endpoints (orgs, tenants, numbers, SIP users, calls, ...)
│   ├── auth/                  # Google OAuth + JWT middleware (org-aware permission helpers)
│   ├── ingestion/             # Twilio WebSocket server + audio decoding
│   ├── transcription/         # Deepgram streaming (two-track) + Whisper (two-track fallback)
│   ├── evaluation/            # Sliding window insight evaluator (direction-aware template filter)
│   ├── broadcaster/           # WebSocket insight broadcaster
│   └── tasks.py               # Celery cold-path pipeline
├── frontend/                  # React + Vite + TypeScript app dashboard
├── marketing/                 # React + Vite marketing site
├── alembic/                   # Database migrations
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## License

Copyright © 2026 Vaughan.Codes (Daniel Vaughan). All rights reserved.

See [LICENSE](LICENSE) for details.
