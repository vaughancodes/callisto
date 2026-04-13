FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN mkdir -p src/callisto && touch src/callisto/__init__.py \
    && pip install --no-cache-dir -e . \
    && rm -rf src/callisto

# Copy application code (changes frequently, never busts dep cache)
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

ENV FLASK_APP=callisto.app:create_app

EXPOSE 5309

CMD ["gunicorn", "-b", "0.0.0.0:5309", "callisto.app:create_app()"]
