# AGENTS.md

Instructions for an AI agent asked to set this dashboard up, run it, or explain it to a human.

## What this repository is

A generator, not a service. `tools/dashboard/build.py` reads a job-search tracker and the application archive, then writes one self-contained HTML file. It makes no network requests and needs no account or API key.

It is an add-on to **[AI Job Search](https://github.com/ai-job-search-dev/ai-job-search)**, which writes the files this dashboard reads. Never assume those files exist.

## Where it installs

The script resolves paths from its own location (two levels up), so it must sit at the root of an AI Job Search repository:

```
<repo>/
├── tools/dashboard/build.py
├── tools/dashboard/template.html
├── job_search_tracker.csv          ← written by /apply and /outcome
└── documents/applications/         ← written by /apply and /outcome
```

Copying the two files into an existing `tools/dashboard/` is the whole installation. There is nothing to `pip install`.

## Decision tree

1. **Is `job_search_tracker.csv` present at the repo root?**
   - **No** → stop. Do not create one from scratch and do not invent rows. Tell the human: the dashboard reads files written by AI Job Search, point them at <https://github.com/ai-job-search-dev/ai-job-search>, and mention that `docs/index.html` in this repository is a demo built from fictional data.
   - **Yes** → continue.
2. **Run the build:**

   ```bash
   python3 tools/dashboard/build.py
   ```

   Optional flags: `--root <dir>` (another repo root), `--out <path>` (another output path).
3. **Read the exit code and stdout.** Success prints `dashboard: <path> (N applications · ...)`. A non-zero exit names the missing input; relay that sentence to the human instead of retrying blindly.
4. **Report** the output path, the counts from stdout, and the reminder that re-running refreshes it after new `/apply` or `/outcome` entries.

## What to tell the human

On success, three things: where the file is, what the counts say, and how to refresh it.

```text
Dashboard generated: reports/dashboard.html
32 applications · 21 applied · 2 interviewing · 8 closed

Open it in any browser. Re-run the script after new applications to refresh it.
```

On missing data, one short paragraph: what the dashboard needs, where it comes from, and the two options (set up the framework, or open the demo to see what it looks like). No stack traces, no speculation.

## Guardrails

- **Never edit `reports/dashboard.html`.** It is generated. Change `tools/dashboard/template.html` and rebuild.
- **Never commit personal data.** `reports/`, `job_search_tracker.csv`, `documents/applications/` and `dashboard.config.json` stay out of git; `.gitignore` already covers them.
- **Never add a network call.** The output must render offline: inline CSS and JS only, no CDN, no fonts, no analytics.
- **Never invent a number.** Every figure in the dashboard comes from the tracker or the archive. If a field is empty, it renders as a dash.
- **Keep the tests honest.** `python3 -m unittest tests.test_dashboard_build` must pass after any change to `build.py` or `template.html`.

## Verification before you claim success

```bash
python3 tools/dashboard/build.py --root sample --out /tmp/demo.html   # if sample/ exists
python3 -m unittest tests.test_dashboard_build
```

Open the generated file and confirm it renders, rather than trusting the exit code alone.
