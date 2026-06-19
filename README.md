# Creator AI Assistant — Bodhisattva Challenge

A chat-assistant website that helps Buddhist content creators script short videos
for **The Bodhisattva Challenge** — a 365-day journey through Śāntideva's
*Bodhicharyavatara*.

The creator picks a day, the app pulls that day's verses, plan, and classical
commentary from a local clone of the source repo, suggests the video ideas that
day's material can support, asks for a duration, and generates a spoken script.
Optionally it turns the script into narrated audio.

## Stack
- **Frontend:** React (Vite) — guided chat UI.
- **Backend:** Django + Django REST Framework.
- **LLM + TTS:** Google Gemini (one API key for both script and audio).
- **Source content:** a local clone of the `bodhisattvacharyavatara-rails` repo.

## Architecture
```
frontend (React/Vite)  ──HTTP──>  backend (Django REST)  ──reads──>  rails repo (markdown)
                                          │
                                          └──> Gemini API (script + audio)
```
The backend reads day-plan + per-verse commentary files, runs one Gemini call to
decide which ideas are available, and fills a per-idea prompt template to generate
the script. No database is used for app data; generated scripts/audio are
ephemeral and flow state lives in the browser.

### Video ideas
| Idea | When offered |
|---|---|
| Concept | always |
| Challenge / Practice | always |
| Testimony (creator supplies notes) | always |
| Story | when the day's material contains one |
| Extra info / fun fact | when the day's material contains one |

## Local setup

### 1. Backend
```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env        # then edit .env
```
Set in `backend/.env`:
- `RAILS_REPO_PATH` — absolute path to your local clone of `bodhisattvacharyavatara-rails`.
- `GEMINI_API_KEY` — your Google Gemini API key (script + audio generation).

Run it:
```bash
venv/bin/python manage.py migrate          # built-in tables only
venv/bin/python manage.py check_content    # verify it can read the rails repo
venv/bin/python manage.py runserver        # http://localhost:8000
```

### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev                 # http://localhost:5173
```

Open http://localhost:5173 and start with a day number (e.g. `5`).

> Without a `GEMINI_API_KEY`, day loading and idea suggestions still work (idea
> availability falls back to a keyword heuristic), but script/audio generation
> returns a clear "not configured" message.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | status + whether Gemini is configured |
| GET | `/api/days/<n>/` | verses, date, plan file, available ideas |
| POST | `/api/script/` | `{day, ideaKey, durationSeconds, creatorNotes?}` → `{script}` |
| POST | `/api/audio/` | `{script, voice?}` → `{audioUrl}` |

## Editing the "skills"
Each video idea is driven by an editable prompt template in
`backend/assistant/prompts/` (`concept.md`, `story.md`, `extra_info.md`,
`testimony.md`, `practice.md`, plus shared `_shared.md` and `assistant.md`).
Tune tone/structure there without touching code.

## Deployment
See [DEPLOY.md](DEPLOY.md) for EC2 (gunicorn + nginx).
