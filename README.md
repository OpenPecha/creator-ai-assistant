# WeBuddhist Creator Assistant — Bodhisattva Challenge

A chat-assistant website that helps Buddhist content creators make short videos
for **The Bodhisattva Challenge** — a 365-day journey through Śāntideva's
*Bodhicharyavatara*.

The creator picks a day; the app pulls that day's verses, plan, and classical
commentary straight from the source GitHub repo, gives a simple plain-language
summary of the verse (in **English** or **हिन्दी Hindi**), suggests the video ideas
that day's material can support, and generates either a ready-to-read **script** or a
shot-by-shot **video structure**. Results can be regenerated, refined by chatting,
and (for scripts) turned into narrated audio.

## Stack
- **Frontend:** React (Vite) — guided chat UI.
- **Backend:** Django + Django REST Framework.
- **LLM + TTS:** Google Gemini (one API key for both text and audio).
- **Source content:** fetched live from the `bodhisattvacharyavatara-rails` GitHub repo.

## Architecture
```
frontend (React/Vite)  ──HTTP──>  backend (Django REST)  ──fetches──>  GitHub (rails repo, raw markdown)
                                          │
                                          └──> Gemini API (summary · script · structure · audio)
```
The backend fetches the day-plan and per-verse commentary files straight from the
`bodhisattvacharyavatara-rails` GitHub repo (no local clone needed — see
`GITHUB_REPO`/`GITHUB_BRANCH` below), with a short in-memory cache so repeat reads
don't re-hit GitHub's API on every request. There's no database for app data —
generated content is ephemeral and flow state lives in the browser. The backend
runs one Gemini call to decide which ideas a day supports, and fills editable
prompt templates ("skills") to generate everything else.

## The creator flow
1. **Pick a day** (1–365).
2. **See the day** — a Day / Chapter / Verses / Date strip plus today's verse text.
3. **Verse summary** — a few short, plain-language bullet points explaining the
   verse. The language toggle (top right) switches the entire experience between
   **English** and **हिन्दी Hindi** — summaries, UI labels, and generated content
   all follow the chosen language.
4. **Pick a verse, then pick a video idea** — each verse expands into a card
   showing the available idea categories as tabs (Commentary, Concept, Challenge,
   Extra info, Creative, Testimony, Story). Commentary and Concept list several
   specific source items (a named commentator's reading, or one of the verse's
   distilled teaching points); tapping one pins the whole video to that exact
   piece of material.
5. **Choose the output type** — **Video script** (a ready-to-read spoken script) or
   **Video structure** (a storyboard: timed beats with on-screen visuals +
   voiceover).
6. **Pick a duration** — 30 / 45 / 60 / 90 seconds. The spoken length scales with
   the choice (~2.5 words/second, split ~20/60/20 across Opening/Middle/End).
7. **Get the result**, then **↻ Regenerate** for a fresh take, or **chat to refine
   it** ("make the hook punchier", "shorten the opening"). Scripts can also be
   turned into **narrated audio**. At any point after picking a category, **‹ Pick
   a different verse or type** jumps back to the verse picker for the same day —
   no reload, no refetch.

### Video structure — three complete versions, not mix-and-match beats
A **Video structure** result is three full alternate storyboards (Version 1/2/3),
each independently planned end-to-end so its own Opening → Middle → End is
internally consistent (a named commentator is introduced once per version, an
End can safely call back to its own Opening's image). The **Version** selector
switches all three beats together — there's no picking, say, Version 2's Opening
with Version 1's Middle, since beats were never designed to mix across versions.

### Video ideas
Each idea category has a distinct SVG tab icon; Commentary and Concept additionally
surface several specific source items to choose from within the tab:

| Idea | What it does | When offered |
|---|---|---|
| **Commentary** | One classical commentator's specific reading of the verse | always |
| **Concept** | Makes one of the verse's distilled teaching points unmistakably clear | always |
| **Challenge** | Invites viewers to do today's practice | always |
| **Extra info** | A surprising detail or metaphor from the texts | when the material contains one |
| **Creative** | A secular, universal video about the *lesson* — no scripture or Buddhist references, for everyone | always |
| **Testimony** | Shapes the creator's own personal notes into a first-person reflection | always |
| **Story** | A story or parable from the source material | when the material contains one |

The backend decides which conditional ideas (Extra info, Story) are available for
a given day via an LLM analysis of the source material.

## Local setup

### Quick start
```bash
make install        # backend venv + deps, frontend npm install
make dev            # runs backend (:8000) and frontend (:5173) together; Ctrl+C stops both
```

### Backend (manual)
```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env        # then edit .env
```
Set in `backend/.env`:
- `GITHUB_REPO` — the content repo (`owner/repo-name`); files are fetched directly
  from GitHub, no local clone needed. Defaults to `webuddhist/bodhisattvacharyavatara-rails`.
- `GITHUB_TOKEN` — optional but recommended (raises the GitHub API rate limit from
  60 to 5000/hour).
- `GEMINI_API_KEY` — your Google Gemini API key (summary, script, structure, audio).

```bash
venv/bin/python manage.py migrate          # built-in tables only
venv/bin/python manage.py check_content    # verify it can read the rails repo
venv/bin/python manage.py runserver 0.0.0.0:8000
```

### Frontend (manual)
```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE_URL defaults to http://localhost:8000
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
| GET | `/api/days/<n>/` | verses, chapter, date, verse text, available ideas, per-verse resources |
| GET | `/api/days/<n>/share-image/` | proxies the day's shareable "today's challenge" image (same-origin, so the browser can display/download it) |
| POST | `/api/verse-summary/` | `{day, language}` → `{points}` — `language` is `english` or `hindi` |
| POST | `/api/script/` | `{day, ideaKey, durationSeconds, language, focus?, focusLabel?, creatorNotes?, feedback?, previous?}` → `{script}` |
| POST | `/api/structure/` | `{day, ideaKey, durationSeconds, language, focus?, focusLabel?, creatorNotes?, feedback?, previous?}` → `{structure}` |
| POST | `/api/audio/` | `{script, voice?}` → `{audioUrl}` |

- `language` — `"english"` or `"hindi"`; passed to all generation endpoints so the
  output is produced in the chosen language end-to-end.
- `focus` / `focusLabel` — optional strings that pin generation to one specific
  source item (e.g. a named commentator's reading, or one teaching point) when
  Commentary/Concept offers several; `focus` is the full text, `focusLabel` the
  short title. Omit both for the day's general material.
- `feedback` + `previous` — power the chat-to-refine step; omit for a fresh generation.
- `structure`'s response holds three fully-planned alternate versions per beat
  (see "Video structure" above) — `sections[].options[]`, index-aligned across beats.

## The "skills" (prompt templates)
Every generation is driven by an editable markdown template in
`backend/assistant/prompts/` — tune tone, structure, and rules without touching
code (changes take effect on the next request, no restart needed):

| File | Role |
|---|---|
| `_shared.md` | Shared, source-faithful context + voice rules for scripts |
| `commentary.md`, `concept.md`, `practice.md`, `testimony.md`, `story.md`, `extra_info.md` | Per-idea script angles |
| `creative.md` | Self-contained Creative script (secular, no source references) |
| `verse_summary.md`, `verse_summary_hindi.md` | Simple plain-language verse summary (English / Hindi) |
| `overview_simplify.md` | Rewrites the classical commentary "overview" blurb into plainer language |
| `structure.md` | Source-faithful video storyboard (three matched versions) |
| `structure_creative.md` | Secular, universal storyboard for the Creative idea |
| `structure_testimony.md` | Storyboard built around the creator's own testimony |
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
