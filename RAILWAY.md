# Deploy OmniVoice chat on Railway

One **Docker** service serves the Vite build from `/` and the FastAPI API under `/api` (same origin, so the existing `fetch('/api/...')` calls keep working).

## Prerequisites

- A [Railway](https://railway.app) account and a Git repo that contains this `omnivoice-chat` folder (either the repo root is this folder, or you set the service **Root Directory** to `omnivoice-chat`).
- An **OpenRouter** API key for Rocky’s LLM.
- **Voice assets**: Rocky’s clone expects `backend/assets/voices/Rocky-2.wav` (see `backend/app/voices.py`). Commit that file or adjust paths before deploy, or TTS will fail at runtime.

## Steps

1. **Push your code** to GitHub (or GitLab / Bitbucket) so Railway can connect.
2. In Railway: **New project** → **Deploy from GitHub** → pick the repo.
3. Open the new service → **Settings** → **Root Directory**: set to `omnivoice-chat` if the repo root is your whole `Projects` tree; leave blank if the repo is only this app.
4. **Settings** → **Build**: Railway should detect `Dockerfile` and `railway.toml` (builder `dockerfile`). No custom start command is required; `CMD` in the Dockerfile runs uvicorn on `$PORT`.
5. **Variables** (service → **Variables**), add at least:
   - `OPENROUTER_API_KEY` — your secret key.
   - Optional: `OPENROUTER_MODEL` (default in code is `openrouter/auto`).
   - Optional: `ROCKY_PROMPT_MAX_CHARS`, `OMNIVOICE_DEVICE` (`cpu` is implicit on Railway).
6. **Resources**: OmniVoice + Whisper are heavy. Use a plan with **enough RAM** (often **≥ 8 GB** for a comfortable first boot; CPU-only TTS will still be slow compared to a local GPU).
7. **Networking**: Generate a **public domain** (Settings → Networking → Generate domain). Open that URL in a normal browser (not the Cursor embedded browser if you rely on Web Speech dictation).
8. **Health check**: `railway.toml` points at `GET /api/health`. After deploy, confirm it returns 200 in the Railway metrics / browser.
9. **Logs**: Watch deploy logs for `pip` / model download errors. First TTS request may take a long time while weights load.
10. **Data**: Session audio and JSONL logs live under `backend/data` in the container filesystem. They are lost on redeploy unless you add a **Railway volume** mounted at `/app/backend/data` (optional follow-up).

## Local Docker sanity check

From the `omnivoice-chat` directory:

```bash
docker build -t omnivoice-chat:test .
docker run --rm -p 8080:8000 -e OPENROUTER_API_KEY=sk-or-... omnivoice-chat:test
```

Open `http://localhost:8080` and try a typed turn.

## Alternative: two Railway services

If you prefer a separate **static** frontend and **API** only:

- Build `frontend` with `npm run build` and deploy `dist/` to a static host (or a tiny static server).
- Point the client at the API by changing the frontend to use a configurable API base URL (not included in this repo’s default `fetch('/api/...')`).

The Dockerfile path above avoids that split by serving the SPA from FastAPI when `FRONTEND_DIST` is set (done automatically in the image).
