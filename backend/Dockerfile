FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: curl for healthcheck, build deps for lxml/matplotlib
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl \
    libxml2-dev \
    libxslt1-dev \
    libfreetype6-dev \
    libpng-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Default storage roots (overridable via env)
ENV VAULT_DATA_DIR=/data/files \
    VAULT_THUMB_DIR=/data/thumbs \
    VAULT_DB_URL=sqlite:////data/db/nexus3d.sqlite

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
