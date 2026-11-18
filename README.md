# Job Search Dashboard

A single-file, offline dashboard for the [AI Job Search](https://github.com/MadsLorentzen/ai-job-search) workflow. It reads your tracker and application archive and writes one self-contained HTML file you can open in any browser.

No server. No account. No API key. Your data never leaves the machine.

**Demo:** open [`demo/index.html`](demo/index.html) locally, or enable GitHub Pages for the `demo/` folder. It is built from the fictional data in `sample/`.

![Dashboard preview](docs/preview.jpg)

---

## What you get

- **Kanban board** of every application, grouped by status, with search and filters.
- **Application drawer** with the posting summary, what changed in the CV, talking points, interview stages and a dated history.
- **Insights**: status treemap, sector ranking, channel split and a conversion funnel.
- **Pace section**: applications per day and per week as line charts, a GitHub-style calendar of daily activity, and a by-month breakdown.
- **Bilingual UI** (PT-BR / EN), light theme, one HTML file of about 90 KB.

## Quick start

1. Copy `tools/dashboard/` into your AI Job Search repo, at the same path:

   ```
   your-repo/
   ├── tools/dashboard/build.py
   ├── tools/dashboard/template.html
   ├── job_search_tracker.csv
   └── documents/applications/
   ```

2. Build it:

   ```bash
   python3 tools/dashboard/build.py
   ```

3. Open `reports/dashboard.html`.

Requirements: Python 3.9 or newer. Standard library only, nothing to install.

## What it reads

| Input | What it is used for |
|---|---|
| `job_search_tracker.csv` | one row per application: company, role, status, dates, fit, notes |
| `documents/applications/<company>_<role>/job_posting.md` | posting summary and requirements in the drawer |
| `documents/applications/<company>_<role>/cv_draft.tex` | the positioning line and skills shown in the drawer |
| `documents/applications/<company>_<role>/outcome.md` | interview stages and dated history |
| `documents/applications/<company>_<role>/dashboard.json` | optional enrichment (see below) |

Tracker columns, in order:

```
date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline
```

Statuses: `drafted`, `applied`, `interview`, `hold`, `offer`, `hired`, `rejected`, `no_response`, `offer_declined`, `withdrawn`.

## Optional enrichment

Drop a `dashboard.json` next to an application to override what the build infers:

```json
{
  "workMode": "remote",
  "skills": ["Design systems", "Research"],
  "requirements": ["Own the component library", "Partner with engineering"],
  "adaptations": ["Led with the platform rebuild"],
  "talkingPoints": ["Bring the accessibility audit"],
  "postingSummary": "One paragraph if the posting is not archived.",
  "interviewDate": "2026-11-18",
  "deadline": "2026-12-01"
}
```

## Configuration

- `dashboard.config.json` at the repo root, optional: `{"ownerName": "Your Name"}` puts your name in the greeting.
- `--root` builds against another folder (used here to build `demo/` from `sample/`).
- `--out` writes the HTML somewhere else.

```bash
python3 tools/dashboard/build.py --root sample --out demo/index.html
```

## Privacy

The build reads your files; it never sends them anywhere. When you use this in a real job search, keep these out of git:

```gitignore
/reports/
/job_search_tracker.csv
/documents/applications/**
/dashboard.config.json
```

The demo in this repository is generated from fictional companies and fictional applications.

## Customising

Everything visual lives in `tools/dashboard/template.html`: palette at the top in `:root`, copy in the `I18N` object, charts in plain JavaScript. Rebuild after editing; never edit `reports/dashboard.html` by hand.

## Tests

```bash
python3 -m unittest tests.test_dashboard_build
```

## License

MIT. See [LICENSE](LICENSE).

Built on the AI Job Search framework by [Mads Lorentzen](https://github.com/MadsLorentzen/ai-job-search). Not affiliated; just happy to give something back.
