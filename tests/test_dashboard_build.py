"""Tests for the interactive dashboard generator (tools/dashboard/build.py).

The board is generated output, so the checks here target the inputs and the
contract: the tracker parses cleanly, every row reaches the data model, the
per-application enrichment files stay valid JSON, and the generated HTML is
self-contained with its data embedded.

The suite runs against a real tracker when the repository has one, and against
the bundled `sample/` data otherwise (the public template repository).
"""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD = REPO_ROOT / "tools" / "dashboard" / "build.py"
TEMPLATE = REPO_ROOT / "tools" / "dashboard" / "template.html"

TRACKER = REPO_ROOT / "job_search_tracker.csv"
APPLICATIONS = REPO_ROOT / "documents" / "applications"
DATA_ROOT = REPO_ROOT

if not TRACKER.is_file():
    DATA_ROOT = REPO_ROOT / "sample"
    TRACKER = DATA_ROOT / "job_search_tracker.csv"
    APPLICATIONS = DATA_ROOT / "documents" / "applications"

sys.path.insert(0, str(REPO_ROOT / "tools" / "dashboard"))
import build as dashboard_build  # noqa: E402

dashboard_build.ROOT = DATA_ROOT
dashboard_build.TRACKER = TRACKER
dashboard_build.APPLICATIONS = APPLICATIONS


class TrackerShapeTests(unittest.TestCase):
    def test_tracker_exists(self):
        self.assertTrue(TRACKER.is_file(), f"tracker not found: {TRACKER}")

    def test_every_row_has_fourteen_fields(self):
        """An extra comma silently shifts cv/cover/source/deadline a column left."""
        with TRACKER.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        widths = sorted({len(row) for row in rows})
        self.assertEqual(widths, [14], f"tracker rows have ragged widths: {widths}")

    def test_status_values_are_known(self):
        with TRACKER.open(newline="", encoding="utf-8") as handle:
            statuses = {(row.get("status") or "").strip().lower() for row in csv.DictReader(handle)}
        unknown = statuses - set(dashboard_build.BUCKETS)
        self.assertEqual(unknown, set(), f"unknown tracker statuses: {sorted(unknown)}")


class DataModelTests(unittest.TestCase):
    def test_every_tracker_row_reaches_the_board(self):
        with TRACKER.open(newline="", encoding="utf-8") as handle:
            expected = sum(1 for _ in csv.DictReader(handle))
        self.assertEqual(len(dashboard_build.build()["apps"]), expected)

    def test_apps_carry_the_fields_the_template_reads(self):
        keys = {
            "id", "company", "role", "sector", "status", "statusRaw", "date",
            "deadline", "fit", "channel", "notes", "source", "cvFile", "workMode",
            "skills", "requirements", "adaptations", "talkingPoints",
            "postingSummary", "cvSubtitle", "cvProfile", "interviewDate",
            "resolved", "outcomeNotes", "stages",
        }
        for app in dashboard_build.build()["apps"]:
            self.assertTrue(keys.issubset(app.keys()), f"{app['company']} missing keys")
            self.assertIn(app["status"], {"drafted", "applied", "interview", "hold", "offer", "hired", "closed"})

    def test_enrichment_files_are_valid_json(self):
        for path in APPLICATIONS.glob("*/dashboard.json"):
            with self.subTest(path=path):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)
                if "workMode" in data:
                    self.assertIn(data["workMode"], {"remote", "hybrid", "onsite", "unknown"})


class GeneratorTests(unittest.TestCase):
    def _build(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dashboard.html"
            result = subprocess.run(
                [sys.executable, str(BUILD), "--root", str(DATA_ROOT), "--out", str(out)],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return out.read_text(encoding="utf-8")

    def test_build_runs_and_embeds_data(self):
        html = self._build()
        self.assertNotIn("/*__DATA__*/null", html)
        self.assertIn("const DATA = {", html)
        self.assertIn("</html>", html)

    def test_output_is_self_contained(self):
        html = self._build()
        self.assertNotIn("http://", html.split("<script>")[0])
        self.assertNotIn("cdn.", html.lower())
        self.assertNotIn("<script src=", html.lower())


if __name__ == "__main__":
    unittest.main()
