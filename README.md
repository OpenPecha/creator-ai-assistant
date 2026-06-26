# WeBuddhist Creator Assistant — Bodhisattva Challenge

A chat-assistant website that helps Buddhist content creators make short videos
for **The Bodhisattva Challenge** — a 365-day journey through Śāntideva's
*Bodhicharyavatara*.

The creator picks a day; the app pulls that day's verses, plan, and classical
commentary from a local clone of the source repo, gives a simple plain-language
summary of the verse (in **English** or **हिन्दी Hindi**), suggests the video ideas
that day's material can support, and generates either a ready-to-read **script** or a
shot-by-shot **video structure**. Results can be regenerated, refined by chatting,
and (for scripts) turned into narrated audio.

## Stack
- **Frontend:** React (Vite) — guided chat UI.
- **Backend:** Django + Django REST Framework.
- **LLM + TTS:** Google Gemini (one API key for both text and audio).
- **Source content:** a local clone of the `bodhisattvacharyavatara-rails` repo.

## Architecture
```
frontend (React/Vite)  ──HTTP──>  backend (Django REST)  ──reads──>  rails repo (markdown)
                                          │
                                          └──> Gemini API (summary · script · structure · audio)
```
The backend reads the day-plan and per-verse commentary files directly from disk
(no database for app data — generated content is ephemeral and flow state lives in
the browser). It runs one Gemini call to decide which ideas a day supports, and
fills editable prompt templates ("skills") to generate everything else.

## The creator flow
1. **Pick a day** (1–365).
2. **See the day** — a Day / Chapter / Verses / Date strip plus today's verse text.
3. **Verse summary** — a few short, plain-language bullet points explaining the
   verse. The language toggle (top right) switches the entire experience between
   **English** and **हिन्दी Hindi** — summaries, UI labels, and generated content
   all follow the chosen language.
4. **Pick a verse, then pick a video idea** — each verse expands into a card
   showing the available idea types as tabs (Story, Concept, Challenge, Extra info,
   Creative, Testimony). Each idea shows one or more specific angles as clickable
   option cards; tapping one commits to that angle and moves forward.
5. **Choose the output type** — **Video script** (a ready-to-read spoken script) or
   **Video structure** (a storyboard: timed beats with on-screen visuals +
   voiceover).
6. **Pick a duration** — 30 / 45 / 60 / 90 seconds.
7. **Get the result**, then **↻ Regenerate** for a fresh take, or **chat to refine
   it** ("make the hook punchier", "shorten the opening"). Scripts can also be
   turned into **narrated audio**.

### Video ideas
Each idea type has a distinct SVG tab icon and may surface multiple angles (e.g.
two Story options appear as "Story 1" and "Story 2"):

| Idea | What it does | When offered |
|---|---|---|
| **Story** | A story or parable from the source material | when the material contains one |
| **Concept** | Explains the core idea of the verse | always |
| **Challenge** | Frames today's practice as a doable dare | always |
| **Extra info** | A surprising detail or fun fact from the texts | when the material contains one |
| **Creative** | A secular, universal video about the *lesson* — no scripture or Buddhist references, for everyone | always |
| **Testimony** | Shapes the creator's own personal notes into a first-person reflection | always |

The backend decides which ideas are available for a given day via an LLM analysis
of the source material; Story and Extra info only appear when the texts genuinely
support them.

## Local setup

### Quick start
```bash
make install        # backend venv + deps, frontend npm install
make dev            # runs backend (:8001) and frontend (:5173) together; Ctrl+C stops both
```

### Backend (manual)
```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env        # then edit .env
```
Set in `backend/.env`:
- `RAILS_REPO_PATH` — absolute path to your local clone of `bodhisattvacharyavatara-rails`.
- `GEMINI_API_KEY` — your Google Gemini API key (summary, script, structure, audio).

```bash
venv/bin/python manage.py migrate          # built-in tables only
venv/bin/python manage.py check_content    # verify it can read the rails repo
venv/bin/python manage.py runserver 0.0.0.0:8001
```

### Frontend (manual)
```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE_URL defaults to http://localhost:8001
npm run dev                 # http://localhost:5173
```

Open http://localhost:5173 and start with a day number (e.g. `5`).

> Without a `GEMINI_API_KEY`, day loading still works and idea availability falls
> back to a keyword heuristic — but the verse summary, script, structure, and audio
> all require Gemini and return a clear "not configured" message.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | status + whether Gemini is configured |
| GET | `/api/days/<n>/` | verses, chapter, date, verse text, available ideas |
| POST | `/api/verse-summary/` | `{day, language}` → `{points}` — `language` is `english` or `hindi` |
| POST | `/api/script/` | `{day, ideaKey, durationSeconds, language, focus?, creatorNotes?, feedback?, previous?}` → `{script}` |
| POST | `/api/structure/` | `{day, ideaKey, durationSeconds, language, focus?, creatorNotes?, feedback?, previous?}` → `{structure}` |
| POST | `/api/audio/` | `{script, voice?}` → `{audioUrl}` |

- `language` — `"english"` or `"hindi"`; passed to all generation endpoints so the
  output is produced in the chosen language end-to-end.
- `focus` — optional object `{text, typeLabel, label}` that pins generation to a
  specific idea angle when a tab offers multiple options (e.g. Story 1 vs Story 2).
- `feedback` + `previous` — power the chat-to-refine step; omit for a fresh generation.

## The "skills" (prompt templates)
Every generation is driven by an editable markdown template in
`backend/assistant/prompts/` — tune tone, structure, and rules without touching
code (changes take effect on the next request, no restart needed):

| File | Role |
|---|---|
| `_shared.md` | Shared, source-faithful context + voice rules for scripts |
| `concept.md`, `practice.md`, `testimony.md`, `story.md`, `extra_info.md` | Per-idea script angles |
| `creative.md` | Self-contained Creative script (secular, no source references) |
| `verse_summary.md` | Simple plain-language verse summary (English/Hindi) |
| `structure.md` | Source-faithful video storyboard |
| `structure_creative.md` | Secular, universal storyboard for the Creative idea |
| `assistant.md` | Greeting / persona |

## Security & limits
- **Rate limiting** — the Gemini-backed endpoints are throttled (default `20/min`
  for generation, `60/min` elsewhere; tune via `THROTTLE_GENERATE` / `THROTTLE_ANON`
  in `.env`) to protect the API budget.
- **Input caps** — `creatorNotes`, `script`, and `feedback` are length-capped.
- **Production guards** — with `ENV=production`, the app refuses to start if
  `DEBUG` is on or `DJANGO_SECRET_KEY` is left at the insecure default.
- **Caching** — day content and idea analysis are cached in memory; identical audio
  requests reuse the existing file. Verse summaries are cached in production and
  regenerated live in local dev.

## Deployment
See [DEPLOY.md](DEPLOY.md) for EC2 (gunicorn + nginx).
