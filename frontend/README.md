# Frontend — WeBuddhist Creator Assistant

React + Vite single-page app. All chat state lives in the browser; the backend is
hit only for content loading and AI generation.

## Stack
- **React 18** — functional components, hooks (`useState`, `useRef`, `useEffect`, `useContext`)
- **Vite** — dev server + production build
- **CSS custom properties** — theme tokens in `:root` (`--bg`, `--ink`, `--border`, etc.)

## Key files
| File | Role |
|---|---|
| `src/App.jsx` | Entire app — state machine, all components, UI text dictionaries |
| `src/App.css` | All styles — layout, components, responsive breakpoints |
| `public/logo.png` | Header logo |

## Architecture
Everything lives in `App.jsx`. Notable pieces:

- **`UI` dictionary** — all user-facing strings keyed by language (`english` / `hindi`).
  Add a new language by adding a key here; no other change needed.
- **`LangContext` / `useUI()`** — passes the active language's strings down to every
  component without prop-drilling.
- **`IDEA_ICONS`** — inline SVG React elements keyed by idea type, used in the verse
  card tabs.
- **`VerseCard`** — expandable card per verse. Shows idea-type tabs; each tab
  surfaces one or more clickable option cards. Tapping an option calls `onChooseIdea`
  with a `focus` object describing the specific angle chosen.
- **`availableIdeas`** — real LLM-generated idea objects from `/api/days/<n>/`, each
  with `key`, `label`, and `teaser`. `VerseCard` builds its tabs entirely from this
  data; there is no mock fallback.

## State machine
The top-level `stage` string drives which UI panel is shown:

| Stage | What the user sees |
|---|---|
| `pickDay` | Day number input |
| `loadingDay` | Loading spinner |
| `pickVerse` | Verse cards with expandable idea tabs |
| `askOutputType` | Video script vs. Video structure choice |
| `askDuration` | Duration chips (30 / 45 / 60 / 90 s) |
| `generating` | Loading spinner |
| `result` | Generated script or structure + actions |
| `refining` | Chat input for refine/regenerate |

## Responsive breakpoints
| Breakpoint | Behaviour |
|---|---|
| > 640px | Header on one row (brand left, controls right) |
| ≤ 640px | Controls (language toggle + progress pill) wrap to a second row |
| ≤ 560px | Reduced padding, smaller header text |
| ≤ 380px | Smaller toggle buttons for very small phones |

The verse idea tabs scroll horizontally with a hidden scrollbar on narrow screens.

## Dev
```bash
npm install
cp .env.example .env    # set VITE_API_BASE_URL=http://localhost:8001
npm run dev             # http://localhost:5173
```

## Build
```bash
npm run build   # outputs dist/
```
Set `VITE_API_BASE_URL` to your production API origin before building.
