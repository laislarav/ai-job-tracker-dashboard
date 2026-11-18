# /dashboard - Rebuild the Interactive Job Board

Regenerate `reports/dashboard.html` from the tracker and the application archives. The page is a single self-contained HTML file: stat cards on top, an Asana-style kanban board, and a detail drawer per application that answers "what did the company ask for, what did I adapt in the CV, and how should I present myself".

This command only reads data and writes the report. It never changes the tracker, the archives, or any profile file.

---

## Step 0: Run the generator

```bash
python3 tools/dashboard/build.py
```

It prints the row count and the per-status summary. If it fails, report the error verbatim; do not hand-edit the HTML.

---

## Step 1: Tell the user what changed

Report, in one or two lines:

- the output path (`reports/dashboard.html`)
- the counts it printed (aplicações, por status)

The page renders offline: no server, no CDN, no external requests.

---

## When to run it

- **After `/apply` creates a CV** - mandatory, as `/apply` Step 6c. This is the "updates whenever a CV is created" contract.
- **After `/outcome` changes a status**, or after any manual edit to `job_search_tracker.csv` that the user cares about.
- **On demand** - whenever the user asks to see the board.

---

## How the detail panel is populated

The generator merges three sources, in this order of authority:

1. **`documents/applications/<company>_<role>/dashboard.json`** (optional, curated) - overrides everything below.
2. **The archive** - `job_posting.md` supplies the posting summary and a heuristic requirements list; `cv_draft.tex` supplies the positioning line and core skills; `outcome.md` supplies stages, dates and notes.
3. **The tracker row** - dates, fit, channel, deadline, notes. Phrases like `tailored to marketplace, checkout, fintech` are recovered automatically as "what was adapted".

### `dashboard.json` schema

All fields are optional. Only write what the archived materials actually support - never invent requirements or adaptations.

```json
{
  "workMode": "remote",
  "skills": ["Fintech", "Mobile nativo", "AI no fluxo"],
  "requirements": ["6-8+ anos de Product Design", "..."],
  "adaptations": ["Case de saque priorizado para responder ao requisito de mobile", "..."],
  "talkingPoints": ["Abra com a PicPay: ...", "..."],
  "postingSummary": "Resumo em uma ou duas frases",
  "interviewDate": "2026-11-17",
  "deadline": "2027-01-08",
  "skillsEn": ["Fintech", "Native mobile", "AI in the workflow"],
  "requirementsEn": ["6-8+ years of Product Design", "..."],
  "adaptationsEn": ["Cash-out case prioritized for the native mobile requirement", "..."],
  "talkingPointsEn": ["Open with PicPay: ...", "..."]
}
```

- `workMode`: `remote` | `hybrid` | `onsite` | `unknown`.
- `cvSubtitleEn`: the English version of the CV positioning line, when the submitted CV used Portuguese.
- Every `*En` field is optional and powers the PT/EN toggle in the board's drawer. When absent, the page falls back to the Portuguese/default list, so only add English when the translation is faithful. Raw history notes are shown behind a "Show original notes" disclosure in EN because they are archived verbatim.
- `requirements`: the short list of what the posting asked for, in the posting's language, deduplicated.
- `adaptations`: what the CV/cover letter changed or emphasized for this role. This is the interview-prep payoff - write it from the actual draft, not from the candidate profile.
- `talkingPoints`: 3-6 concrete openings, ordered, each one sentence. Grounded in the submitted materials only.

`/apply` Step 6c writes this file when the posting and drafts give it enough to say something true. When they don't, leave it absent - the page degrades gracefully and tells the user to run `/interview <company>`.

---

## Design rules for anyone editing the generator

- Charts and layout are hand-written; no chart library, no CDN.
- Escape every value before interpolating it into HTML (company names and notes contain `&`, `<`, quotes).
- Keep the board usable with an empty or tiny tracker: columns still render, cards are the primary value.
- Never fabricate a number, a requirement, or a talking point. Every field either comes from a file or is absent.
