FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    SOBAT_ENV=production \
    SOBAT_CORS_ORIGINS='["*"]'

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/api/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/data/var/audio /app/data/var/uploads

EXPOSE 10000

CMD ["sh", "-c", "uvicorn api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]
