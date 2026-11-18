#!/usr/bin/env python3
"""Build the interactive job-search dashboard.

Reads job_search_tracker.csv plus the per-application archive
(documents/applications/<company>_<role>/) and writes a single
self-contained HTML file to reports/dashboard.html.

Run this after creating or updating a CV so the board stays current:

    python3 tools/dashboard/build.py

Optional per-application enrichment lives in
documents/applications/<company>_<role>/dashboard.json:

    {
      "workMode": "remote",                      // remote | hybrid | onsite
      "skills": ["Fintech", "Design systems"],
      "requirements": ["...", "..."],
      "adaptations": ["...", "..."],
      "talkingPoints": ["...", "..."],
      "postingSummary": "...",
      "interviewDate": "2026-11-17",
      "deadline": "2027-01-08"
    }

Every field is optional and overrides what the script infers from the
archived posting, CV draft and outcome file.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "job_search_tracker.csv"
APPLICATIONS = ROOT / "documents" / "applications"
TEMPLATE = Path(__file__).resolve().parent / "template.html"
OUTPUT = ROOT / "reports" / "dashboard.html"

BUCKETS = {
    "drafted": "drafted",
    "applied": "applied",
    "interview": "interview",
    "on_hold": "hold",
    "on hold": "hold",
    "aguardando": "hold",
    "waiting": "hold",
    "hold": "hold",
    "offer": "offer",
    "hired": "hired",
    "rejected": "closed",
    "no_response": "closed",
    "no response": "closed",
    "offer_declined": "closed",
    "offer declined": "closed",
    "withdrawn": "closed",
}

SECTOR_BY_RAW = {
    "climate tech": "other",
    "staff augmentation (client: global insights and strategy firm)": "consulting",
    "staff augmentation (client: us personal finance platform)": "consulting",
    "industrial software / frontline operations (autodesk)": "saas",
    "e-commerce and fintech for smbs": "ecommerce",
    "fintech e meios de pagamento": "fintech",
    "software / digital products": "saas",
    "hr and payroll saas": "saas",
    "consumer software": "saas",
    "technology consultancy and software outsourcing": "consulting",
    "crypto / bitcoin-backed lending (fintech)": "fintech",
    "ai services and nearshore software development": "ai",
    "non-profit / free knowledge": "other",
    "sports retail / e-commerce (centauro, fisia)": "ecommerce",
    "health tech (stealth-stage startup)": "health",
    "media / staffing (via collabera)": "consulting",
    "hr tech / ai-native hr": "saas",
    "overseas contractor staffing": "consulting",
    "ai data services and talent marketplace": "ai",
    "healthcare saas": "health",
    "industrial asset management software": "saas",
    "ai sales platform": "ai",
    "fintech": "fintech",
    "social media and big tech": "other",
    "enterprise saas and crm": "saas",
    "software consultancy": "consulting",
    "technology consultancy": "consulting",
    "fintech and financial services": "fintech",
    "job platform with ai matching": "ai",
    "unknown - not researched": "unknown",
}

ROLE_EN_REPLACEMENTS = [
    ("Sênior", "Senior"),
    ("Pleno", "Mid-level"),
    ("Júnior", "Junior"),
    ("Designer de Produto", "Product Designer"),
    ("UI/UX", "UI/UX"),
]

REQUIREMENT_HINTS = re.compile(
    r"\b(experience|experienced|proven|track record|knowledge|ability|familiar|"
    r"strong|years|hands-on|expertise|background|degree|fluen|proficien|"
    r"experi[eê]ncia|conhecimento|viv[eê]ncia|dom[ií]nio|ingl[eê]s|portugu[eê]s|"
    r"buscamos|requisitos|you bring|you have|must have|what we look)\b",
    re.IGNORECASE,
)
STRONG_HINTS = re.compile(
    r"(\d+\+?\s*(?:years|anos)|\bmust\b|proven|expertise|fluen|proficien|"
    r"experience (?:in|with|designing)|experi[eê]ncia|dom[ií]nio|requisitos|"
    r"you bring|you have|we are looking for|buscamos)",
    re.IGNORECASE,
)
SKIP_SENTENCE = re.compile(
    r"^(by applying|job summary|about the job|about us|who we are|we are|our mission|"
    r"the opportunity|what we offer|benefits|compensation|equal opportunity|"
    r"come join|apply now|this is a remote role and)",
    re.IGNORECASE,
)


def slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_latex(text: str) -> str:
    text = re.sub(r"\\(?:textbf|textit|emph|underline)\{([^{}]*)\}", r"\1", text)
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_")
    text = text.replace("---", "—").replace("--", "–").replace("``", '"').replace("''", '"')
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("{", "").replace("}", "")
    return collapse(text)


def find_archive(company: str, role: str, folders: list[Path]) -> Path | None:
    company_slug = slug(company)
    role_slug = slug(role)
    exact = APPLICATIONS / f"{company_slug}_{role_slug}"
    if exact.is_dir():
        return exact

    # "Acme (Labs)" should still find "acme_labs_senior_product_designer".
    aliases = {company_slug}
    base = re.split(r"[(/–—-]", company, maxsplit=1)[0]
    if slug(base):
        aliases.add(slug(base))

    best, best_score = None, 0.0
    for folder in folders:
        name = folder.name
        prefix = next((a for a in aliases if name.startswith(a)), None)
        if not prefix:
            continue
        remainder = name[len(prefix):].strip("_")
        score = SequenceMatcher(None, role_slug, remainder).ratio()
        if role_slug and role_slug in remainder:
            score = max(score, 0.9)
        if score > best_score:
            best, best_score = folder, score
    return best if best_score >= 0.45 else None


def clean_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    return text


def parse_posting(path: Path) -> tuple[str, list[str]]:
    raw = read(path)
    if not raw.strip():
        return "", []
    text = re.split(r"\n##\s*posting_guard", raw, maxsplit=1)[0]
    text = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    text = clean_markdown(text)
    text = re.sub(r"([A-Z][A-Z /&]{6,}:)", r"\n\1 ", text)

    summary = collapse(text)
    if len(summary) > 480:
        summary = summary[:480].rsplit(" ", 1)[0] + "…"

    requirements: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        candidate = collapse(candidate).strip(" -•*·")
        if not (28 <= len(candidate) <= 240):
            return
        key = candidate.lower()[:90]
        if key in seen:
            return
        seen.add(key)
        requirements.append(candidate)

    for line in text.splitlines():
        if re.match(r"^\s*[-•*·]\s+\S", line):
            add(re.sub(r"^\s*[-•*·]\s+", "", line))

    if len(requirements) < 4:
        strong: list[str] = []
        weak: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", collapse(text)):
            if len(sentence) < 28 or SKIP_SENTENCE.search(sentence):
                continue
            if STRONG_HINTS.search(sentence):
                strong.append(sentence)
            elif REQUIREMENT_HINTS.search(sentence):
                weak.append(sentence)
        for sentence in (strong + weak)[: max(0, 8 - len(requirements))]:
            add(sentence)

    return summary, requirements[:8]



def parse_cv(path: Path) -> dict:
    raw = read(path)
    if not raw.strip():
        return {}
    info: dict = {}

    subtitle = re.search(r"\\rsubtitle\{([^{}]*)\}", raw)
    if subtitle:
        info["subtitle"] = strip_latex(subtitle.group(1))

    profile_match = re.search(r"\\rsection\{Profile\}(.*?)(?=\\rsection\{|\\end\{document\})", raw, re.S)
    if profile_match:
        info["profile"] = strip_latex(profile_match.group(1))[:900]

    skills_block = re.search(r"\\rsection\{Core Skills\}(.*?)(?=\\rsection\{|\\end\{document\})", raw, re.S)
    if skills_block:
        leads = re.findall(r"\\item\s+\\textbf\{([^{}]*)\}", skills_block.group(1))
        cleaned = []
        for lead in leads:
            label = collapse(strip_latex(lead)).split(" - ")[0]
            if len(label) > 42:
                label = label[:42].rsplit(" ", 1)[0]
            cleaned.append(label)
        info["skills"] = cleaned[:5]

    return info


def parse_outcome(path: Path) -> dict:
    raw = read(path)
    if not raw.strip():
        return {}
    info: dict = {}

    status = re.search(r"\*\*Status:\*\*\s*(\S+)", raw)
    if status:
        info["status"] = status.group(1)

    resolved = re.search(r"\*\*Date resolved:\*\*\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", raw)
    if resolved:
        info["resolved"] = resolved.group(1)

    stages = []
    interview_dates = []
    for line in raw.splitlines():
        match = re.match(r"^\s*-\s*\[([ xX])\]\s*(.+)$", line)
        if not match:
            continue
        done = match.group(1).lower() == "x"
        label = collapse(match.group(2))
        stages.append({"label": re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", label), "done": done})
        if done and re.search(r"interview|screen|entrevista|conversa|papo|chat", label, re.I):
            found = re.findall(r"\d{4}-\d{2}-\d{2}", label)
            if found:
                interview_dates.append(max(found))

    if stages:
        info["stages"] = stages
    if interview_dates:
        info["interviewDate"] = max(interview_dates)

    notes = re.split(r"^##\s*Notes\s*$", raw, maxsplit=1, flags=re.MULTILINE)
    if len(notes) == 2:
        info["notes"] = collapse(notes[1])[:1600]

    return info


def detect_work_mode(text: str) -> str:
    low = text.lower()
    if re.search(r"hybrid|h[ií]brid", low):
        return "hybrid"
    if re.search(r"on-?site|presencial", low):
        return "onsite"
    if re.search(r"\bremote\b|remoto|remote-first", low):
        return "remote"
    return ""


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(read(path))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def adaptations_from_notes(notes: str) -> list[str]:
    """Recover 'tailored to ...' phrases written by /apply into the tracker or outcome notes."""
    found: list[str] = []
    pattern = r"tailor(?:ed|ing)[^.;]{0,30}?\b(?:to|around)\s+([^.;]{12,240})"
    for match in re.finditer(pattern, notes, re.I):
        blob = match.group(1)
        if re.match(r"\s*(confirm|apply|avoid|make|ensure|keep)\b", blob, re.I):
            continue
        for part in re.split(r",\s*(?:and\s+)?|\s+and\s+", blob):
            part = collapse(part).strip(" .")
            if 3 <= len(part) <= 90 and part.lower() not in {p.lower() for p in found}:
                found.append(part)
    return found[:6]


def sector_key(raw: str) -> str:
    value = collapse(raw).lower()
    if value in SECTOR_BY_RAW:
        return SECTOR_BY_RAW[value]
    for needle, key in (
        ("fintech", "fintech"), ("payments", "fintech"), ("crypto", "fintech"),
        ("e-commerce", "ecommerce"), ("marketplace", "ecommerce"), ("retail", "ecommerce"),
        ("health", "health"),
        ("consult", "consulting"), ("staffing", "consulting"), ("outsourc", "consulting"),
        ("ai ", "ai"), ("data", "ai"),
        ("non-profit", "other"), ("media", "other"),
        ("software", "saas"), ("saas", "saas"), ("b2b", "saas"),
    ):
        if needle in value:
            return key
    return "unknown"


def role_en(role: str) -> str:
    text = role
    for source, target in ROLE_EN_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def reached_interview(bucket: str, stages: list[dict]) -> bool:
    if bucket in {"interview", "hold", "offer", "hired"}:
        return True
    pattern = r"phone screen|first interview|technical interview|case interview|final round|interview|entrevista|conversa|chat"
    return any(
        stage.get("done") and re.search(pattern, stage.get("label", ""), re.I)
        for stage in stages
    )


def _clean_note_text(text: str) -> str:
    text = re.sub(r"\*\*|__|`", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -–—:;,")


def _note_segments(text: str) -> list[str]:
    parts: list[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        parts.extend(re.split(r"\s+-\s+", line))
    return [p.strip() for p in parts if p.strip()]


def _classify_event(text: str) -> str:
    low = text.lower()
    if re.search(r"\bhired\b|contratad", low):
        return "hired"
    if re.search(r"\boffer\b|oferta", low):
        return "offer"
    if re.search(r"rejected|rejei|recusad|role closed|not moving forward", low):
        return "rejected"
    if re.search(r"on[ _]hold|moved to on_hold|aguardando|talent pool|hold until", low):
        return "hold"
    if re.search(r"interview|entrevista|first chat|papo|conversa|chat with", low):
        return "interview"
    if re.search(r"screening|triagem|task round|questionnaire|questionário|certifica", low):
        return "process"
    if re.search(r"follow.?up", low):
        return "followup"
    if re.search(r"\bapplied\b|application received|candidatura|forwarded to requisition|submitted", low):
        return "applied"
    return "note"


KIND_ORDER = {"applied": 0, "process": 1, "interview": 2, "hold": 3, "followup": 4,
              "offer": 5, "hired": 6, "rejected": 7, "note": 8}
BARE_EVENT_TEXT = {"applied", "application sent", "application submitted", "rejected",
                   "interview", "offer", "hired", "on hold", "em espera"}


def parse_history(tracker_notes: str, outcome_notes: str, applied_date: str = "") -> tuple[list[dict], list[str]]:
    """Turn the raw note blobs into dated timeline events plus undated context.

    Both sources are read; events need a date to enter the timeline, everything
    else becomes scannable context (fit, gaps, tailoring decisions).
    """
    events: list[dict] = []
    context: list[str] = []

    for raw in (outcome_notes, tracker_notes):
        for part in _note_segments(raw):
            match = re.search(r"\d{4}-\d{2}-\d{2}", part)
            date = match.group(0) if match else None
            text = part
            if match:
                text = part[: match.start()] + " " + part[match.end():]
            text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
            text = _clean_note_text(text)
            if len(text) < 3:
                continue
            kind = _classify_event(text)
            if text.lower().strip(" .") in BARE_EVENT_TEXT:
                text = ""
            anchored = bool(match) and (match.start() <= 40 or len(part) <= 120)
            if date and anchored and kind != "note":
                events.append({"date": date, "kind": kind, "text": text[:260]})
            elif 12 <= len(text) <= 220 and "?" not in text and not re.match(r"^(posting|source)\b", text, re.I) \
                    and not re.search(r"documents/applications|https?://|cv/main|cover_letters", text):
                context.append(text)

    if applied_date and not any(event["kind"] == "applied" for event in events):
        events.insert(0, {"date": applied_date, "kind": "applied", "text": ""})

    merged: dict[tuple, dict] = {}
    terminal: dict[str, dict] = {}
    for event in events:
        if event["kind"] in {"rejected", "offer", "hired"}:
            current = terminal.get(event["kind"])
            if current is None or (event["date"] or "") < (current["date"] or ""):
                terminal[event["kind"]] = event
            continue
        key = (event["date"], event["kind"])
        if key not in merged or len(event["text"]) > len(merged[key]["text"]):
            merged[key] = event
    for event in terminal.values():
        merged[(event["date"], event["kind"])] = event

    dated = sorted(merged.values(), key=lambda entry: (entry["date"] or "", KIND_ORDER.get(entry["kind"], 9)))

    deduped: list[str] = []
    for text in context:
        if text not in deduped:
            deduped.append(text)
    return dated[:24], deduped[:8]


def build() -> dict:
    with TRACKER.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    folders = sorted(p for p in APPLICATIONS.iterdir() if p.is_dir()) if APPLICATIONS.is_dir() else []
    apps = []

    for index, row in enumerate(rows):
        company = (row.get("company") or "").strip()
        role = (row.get("role") or "").strip()
        raw_status = (row.get("status") or "").strip()
        bucket = BUCKETS.get(raw_status.lower(), "closed")
        archive = find_archive(company, role, folders) if company and role else None
        extra = load_json(archive / "dashboard.json") if archive else {}

        posting_summary, requirements = ("", [])
        cv_info: dict = {}
        outcome: dict = {}
        if archive:
            posting_summary, requirements = parse_posting(archive / "job_posting.md")
            outcome = parse_outcome(archive / "outcome.md")

        cv_path = archive / "cv_draft.tex" if archive else None
        if not cv_path or not cv_path.is_file():
            tracked_cv = (row.get("cv_file") or "").strip()
            if tracked_cv and (ROOT / tracked_cv).is_file():
                cv_path = ROOT / tracked_cv
        if cv_path and cv_path.is_file():
            cv_info = parse_cv(cv_path)

        notes = (row.get("notes") or "").strip()
        corpus = " ".join([notes, posting_summary, cv_info.get("subtitle", "")])
        history, context = parse_history(notes, outcome.get("notes", ""), (row.get("date") or "").strip())

        fit_raw = (row.get("fit_rating") or "").strip()
        fit = int(fit_raw) if fit_raw.isdigit() else None

        apps.append({
            "id": f"app-{index}",
            "company": company,
            "role": role,
            "sector": (row.get("sector") or "").strip(),
            "sectorKey": sector_key((row.get("sector") or "").strip()),
            "status": bucket,
            "statusRaw": raw_status,
            "date": (row.get("date") or "").strip(),
            "deadline": extra.get("deadline") or (row.get("deadline") or "").strip(),
            "fit": fit,
            "channel": (row.get("channel") or "").strip(),
            "channelKey": "" if bucket == "drafted" else "online",
            "reachedInterview": reached_interview(bucket, outcome.get("stages", [])),
            "roleEn": role_en(role),
            "notes": notes,
            "source": (row.get("source") or "").strip(),
            "cvFile": (row.get("cv_file") or "").strip(),
            "workMode": extra.get("workMode") or detect_work_mode(corpus),
            "skills": extra.get("skills") or cv_info.get("skills", []),
            "skillsEn": extra.get("skillsEn", []),
            "requirements": extra.get("requirements") or requirements,
            "requirementsEn": extra.get("requirementsEn", []),
            "adaptations": extra.get("adaptations") or adaptations_from_notes(notes + " " + outcome.get("notes", "")),
            "adaptationsEn": extra.get("adaptationsEn", []),
            "talkingPoints": extra.get("talkingPoints") or [],
            "talkingPointsEn": extra.get("talkingPointsEn", []),
            "postingSummary": extra.get("postingSummary") or posting_summary,
            "cvSubtitle": cv_info.get("subtitle", ""),
            "cvSubtitleEn": extra.get("cvSubtitleEn", ""),
            "cvProfile": cv_info.get("profile", ""),
            "interviewDate": extra.get("interviewDate") or outcome.get("interviewDate", ""),
            "resolved": outcome.get("resolved", ""),
            "outcomeNotes": outcome.get("notes", ""),
            "stages": outcome.get("stages", []),
            "history": history,
            "context": context,
        })

    config_path = ROOT / "dashboard.config.json"
    owner_name = ""
    if config_path.is_file():
        try:
            owner_name = (json.loads(config_path.read_text(encoding="utf-8")) or {}).get("ownerName", "") or ""
        except (ValueError, OSError):
            owner_name = ""

    now = datetime.now()
    started_dates = []
    for app in apps:
        try:
            started_dates.append(datetime.strptime(app["date"], "%Y-%m-%d"))
        except (TypeError, ValueError):
            continue
    started = min(started_dates) if started_dates else None
    days_searching = (now.date() - started.date()).days + 1 if started else 0
    submitted = sum(1 for app in apps if app["status"] != "drafted")
    weeks = max(days_searching, 1) / 7

    return {
        "ownerName": owner_name.strip(),
        "generated": now.isoformat(timespec="seconds"),
        "generatedLabel": now.strftime("%d/%m/%Y às %H:%M"),
        "startedDate": started.strftime("%Y-%m-%d") if started else "",
        "startedLabel": started.strftime("%d/%m/%Y") if started else "",
        "daysSearching": days_searching,
        "appsPerWeek": round(submitted / weeks, 1) if submitted else 0,
        "apps": apps,
    }


def main(argv=None) -> None:
    global ROOT, TRACKER, APPLICATIONS, OUTPUT
    parser = argparse.ArgumentParser(description="Build the job-search dashboard.")
    parser.add_argument("--root", type=Path, default=None,
                        help="repo root holding job_search_tracker.csv (default: two levels above this file)")
    parser.add_argument("--out", type=Path, default=None,
                        help="output HTML path (default: <root>/reports/dashboard.html)")
    args = parser.parse_args(argv)
    if args.root:
        ROOT = args.root.resolve()
        TRACKER = ROOT / "job_search_tracker.csv"
        APPLICATIONS = ROOT / "documents" / "applications"
        OUTPUT = ROOT / "reports" / "dashboard.html"
    if args.out:
        OUTPUT = args.out.resolve()

    if not TRACKER.is_file():
        raise SystemExit(f"tracker not found: {TRACKER}")

    data = build()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    if "/*__DATA__*/null" not in html:
        raise SystemExit("template placeholder not found")
    html = html.replace("/*__DATA__*/null", payload)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")

    buckets: dict[str, int] = {}
    for app in data["apps"]:
        buckets[app["status"]] = buckets.get(app["status"], 0) + 1
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(buckets.items()))
    try:
        shown = OUTPUT.relative_to(ROOT)
    except ValueError:
        shown = OUTPUT
    print(f"dashboard: {shown} ({len(data['apps'])} aplicações · {summary})")


if __name__ == "__main__":
    main()
