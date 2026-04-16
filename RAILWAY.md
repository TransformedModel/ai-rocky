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
   - Optional: **`HF_TOKEN`** — Hugging Face token for higher Hub rate limits and faster model downloads (otherwise you may see “unauthenticated requests” in logs).
   - Optional: **`OMNIVOICE_WARM_START=1`** — only on **large** plans: preloads OmniVoice in a background thread at boot. **Do not** set this on small RAM tiers; see troubleshooting below.
6. **Resources**: OmniVoice (torch) is heavy. Use a plan with **enough RAM** (often **≥ 8 GB** for a comfortable first boot; CPU-only TTS will still be slow compared to a local GPU).
7. **Networking**: Generate a **public domain** (Settings → Networking → Generate domain). Open that URL in a normal browser (not the Cursor embedded browser if you rely on Web Speech dictation).
8. **Health check**: point your service health check at **`GET /api/health`** (if you configure one in the Railway UI). Confirm it returns 200 after deploy.
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

## Troubleshooting: 502 and a restart loop in logs

If logs repeat **“Started server process”** / **“Application startup complete”** and the UI shows **502** on **`/api/conversation/start`**, the container is probably **exiting and restarting** (often **OOM**).

A common trigger was **background OmniVoice warm start** at boot: loading full torch weights right after startup spikes memory and can kill small instances before they serve traffic. **On Railway, warm start is now skipped by default** unless you set **`OMNIVOICE_WARM_START=1`** (use only with enough RAM, e.g. 8 GB+).

After deploy, **`POST /api/conversation/start`** should return quickly. The **first** **`reply-turn`** (TTS) still downloads and loads the model; that request can take **many minutes** on CPU and may hit HTTP timeouts unless the client or proxy allows long waits. **`HF_TOKEN`** reduces Hub throttling during that load.

The Docker image installs **`ffmpeg`** so **pydub** (pulled in transitively) does not spam **RuntimeWarning** about missing `ffmpeg`; that warning was not the root cause of the 502 by itself.
