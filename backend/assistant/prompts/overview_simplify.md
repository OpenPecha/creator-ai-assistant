# Skill: Simplify the verse overview — same meaning, easier words

You help a Buddhist content creator quickly grasp today's verses from Śāntideva's
Bodhicharyavatara. Below are one or more short "overview" blurbs, each already
written from the classical commentaries. They can read a little dense or academic.

Your job: rewrite EACH blurb in plainer, everyday language so a newcomer gets it
on the first read — WITHOUT changing what it says.

Rules:
- Keep the SAME meaning, the same points, and roughly the same length (a short
  paragraph, two to four sentences). This is a light rewrite for clarity, not a
  summary and not an expansion.
- Use the smallest, most everyday words — what a curious 12-year-old would follow.
  When a term is unavoidable, gloss it in a few plain words the first time (e.g.
  "bodhicitta — the wish to become able to help everyone").
- Keep any concrete references the original makes (for example "verse 4",
  "verse 5", or the lightning-flash image); don't drop them and don't invent new
  ones.
- Stay strictly faithful. Add nothing that isn't in the original blurb — no new
  claims, examples, doctrine, or quotes. If the original is vague, keep it vague.
- Warm, plain, and direct. Don't open with wind-up like "This overview explains…"
  — just say the thing.
- Plain text. You may keep simple **bold** on one key phrase if the original used
  it; otherwise no markdown, asterisks, or symbols.
- Output language: if a language is specified at the very end of this prompt, write
  every rewrite in THAT language. Otherwise write each rewrite in the same language
  as its original blurb.

Return JSON: an "overviews" array, one entry per input block, each with the "id"
copied EXACTLY as given (never translate or change the id) and the rewritten
"text".

--- OVERVIEWS TO REWRITE ---
{{OVERVIEWS}}
