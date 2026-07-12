# Python AI service — build context = this directory (backend/ai-service-python/)
FROM python:3.14-slim

# Faster, cleaner Python in a container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
# NOTE: if a dependency has no cp314 wheel and tries to build from source,
# uncomment the build-tools line below.
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code (lib/, app.py, main.py, prompts.yaml, …). .dockerignore keeps
# .env, .venv, *.db, *.log, __pycache__ out of the image.
COPY . .

# The SQLite cache lives on a mounted Fly volume so it survives restarts.
# TRANSLATION_DB_PATH is set to /data/... in fly.toml.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
