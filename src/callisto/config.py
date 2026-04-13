import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:dev@localhost:5433/callisto"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": 5,
    }

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")

    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")

    # Ingestion gateway host — used in TwiML to tell Twilio where to stream audio
    INGESTION_WS_HOST = os.environ.get("INGESTION_WS_HOST", "localhost:5310")

    # LLM — any OpenAI-compatible endpoint
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    # STT provider: "deepgram", "whisper", or "auto"
    STT_PROVIDER = os.environ.get("STT_PROVIDER", "auto")

    # Deepgram (streaming transcription)
    DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

    # Whisper
    WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
    WHISPER_API_URL = os.environ.get("WHISPER_API_URL", "")
    WHISPER_SEGMENT_SECONDS = int(os.environ.get("WHISPER_SEGMENT_SECONDS", "10"))

    # Broadcaster
    BROADCASTER_PORT = int(os.environ.get("BROADCASTER_PORT", "5311"))

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:5309/auth/google/callback"
    )

    # JWT
    JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

    # Superadmin emails (comma-separated) — these users get is_superadmin=True on first login
    SUPERADMIN_EMAILS = [
        e.strip() for e in os.environ.get("SUPERADMIN_EMAILS", "").split(",") if e.strip()
    ]

    # Frontend
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5308")

    CELERY = {
        "broker_url": os.environ.get("REDIS_URL", "redis://localhost:6380/0"),
        "result_backend": os.environ.get("REDIS_URL", "redis://localhost:6380/0"),
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "task_track_started": True,
    }
