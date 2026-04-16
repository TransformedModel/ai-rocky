# syntax=docker/dockerfile:1
# Single service: FastAPI + Vite static (same origin `/api` + SPA).
# Build from repo root `omnivoice-chat/` (this directory).

FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

ENV FRONTEND_DIST=/app/static
COPY --from=frontend /src/frontend/dist /app/static

WORKDIR /app
COPY Rocky /app/Rocky
COPY backend /app/backend

WORKDIR /app/backend
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
  && pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir "omnivoice>=0.1.4"

EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
