# OmniVoice chat (Rocky conversation)

## Setup

### Backend env vars

Create `omnivoice-chat/backend/.env`:

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openrouter/auto
```

### Rocky persona (LLM)

Edit markdown under [`Rocky/`](Rocky/):

- `Rocky-Life.md` backstory and personality
- `Rocky-Speech-Style.md` how Rocky writes and speaks in dialogue

The backend injects both into Rocky’s system prompt when non-empty. It reloads them automatically when you save a file (same `mtime` cache; no restart needed). Very long files are truncated; override the per-file cap with `ROCKY_PROMPT_MAX_CHARS` (default `12000`) in `.env` if you need more.

The system prompt also states up front that this Rocky is the Eridian from *Project Hail Mary*, not Rocky Balboa, so models don’t default to the boxer persona. If `Rocky-Life.md` is missing on the machine running uvicorn, check the server log for a one-time warning; the markdown must live next to `backend/` under `omnivoice-chat/Rocky/`.

OmniVoice still clones timbre from `assets/voices/Rocky-1.wav` and its reference transcript; a short optional `instruct` tag is also passed for Rocky at TTS time.

### Speech input (no server STT)

The backend does **not** run Whisper or other server-side transcription. **Web Speech dictation** plus typing fill the composer; if dictation is empty after a mic take, the UI asks you to **type what you said** and send again while keeping the pending clip for playback on the user bubble.

### Browser dictation (Web Speech API)

Voice turns use **on-device dictation** in parallel with the recorder (`SpeechRecognition` / `webkitSpeechRecognition`) when the browser exposes it.

- Support varies: Chromium-based browsers usually work; Safari differs; Firefox support is spotty.
- Dictation is **not** always offline. The engine may send audio to the OS or browser vendor; treat it like any cloud-adjacent speech feature for privacy expectations.

### Hosting on Railway

Step-by-step deploy (Docker, one public URL, same-origin `/api`) is in [`RAILWAY.md`](RAILWAY.md).

OmniVoice TTS is **CPU-heavy** on Railway; use enough **RAM** for the model and expect slower speech than on a local GPU. There is no server-side STT in this stack; dictation quality depends on the user’s browser.

### Run

Backend:

```bash
cd omnivoice-chat/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

Frontend:

```bash
cd omnivoice-chat/frontend
npm run dev
```

Open the Vite URL. A server session starts automatically the first time you record or send a typed message.

**Chat avatars:** add `rocky.png` and `user.png` under [`frontend/public/avatars/`](frontend/public/avatars/) (see that folder’s `README.txt`).

