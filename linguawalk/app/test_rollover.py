import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "rollover-test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from app import start_session
from consolidation import consolidate_due_periods
from db import get_db, init_db
from learning import record_grammar_event, record_vocabulary_event
from models import GrammarEventRequest, StartSessionRequest, VocabularyEventRequest
from test_support import reset_learning_data


class AutomaticRolloverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db() as db:
            reset_learning_data(db)

    def test_session_start_consolidates_due_periods_once(self):
        with get_db() as db:
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('august', '2026-08-20T08:00:00+00:00',
                           'FRENCH', 'ENGLISH', 'MORNING_WALK')"""
            )
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('current', '2026-09-15T08:00:00+00:00',
                           'FRENCH', 'ENGLISH', 'MORNING_WALK')"""
            )
            record_vocabulary_event(
                db,
                VocabularyEventRequest(
                    session_id="august",
                    language="FRENCH",
                    key="pourtant",
                    event_type="FAILURE",
                    occurred_at="2026-08-20T08:05:00+00:00",
                ),
            )
            record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="current",
                    key="depuis + present",
                    event_type="LEARNING_ERROR",
                    occurred_at="2026-09-15T08:05:00+00:00",
                ),
            )

        with patch("app.utc_now", return_value="2026-09-20T09:00:00+00:00"):
            first = start_session(StartSessionRequest())
            retry = start_session(StartSessionRequest())

        self.assertTrue(first.maintenance.weekly_consolidation_performed)
        self.assertTrue(first.maintenance.monthly_consolidation_performed)
        self.assertFalse(retry.maintenance.weekly_consolidation_performed)
        self.assertFalse(retry.maintenance.monthly_consolidation_performed)

        with get_db() as db:
            weekly_periods = {
                row["week"] for row in db.execute("SELECT week FROM weekly_summaries")
            }
            monthly_periods = {
                row["month"] for row in db.execute("SELECT month FROM monthly_summaries")
            }
            august_archived_at = db.execute(
                "SELECT archived_at FROM vocabulary_events"
            ).fetchone()[0]
            current_archived_at = db.execute(
                "SELECT archived_at FROM grammar_events"
            ).fetchone()[0]

        self.assertEqual(weekly_periods, {"2026-W34", "2026-W37"})
        self.assertEqual(monthly_periods, {"2026-08"})
        self.assertEqual(august_archived_at, "2026-09-20T09:00:00+00:00")
        self.assertIsNone(current_archived_at)

    def test_rollover_uses_previous_iso_periods_across_year_boundary(self):
        with get_db() as db:
            result = consolidate_due_periods(
                db,
                today=date(2026, 1, 1),
                consolidated_at="2026-01-01T08:00:00+00:00",
            )
            week = db.execute("SELECT week FROM weekly_summaries").fetchone()[0]
            month = db.execute("SELECT month FROM monthly_summaries").fetchone()[0]

        self.assertTrue(result.weekly_consolidation_performed)
        self.assertTrue(result.monthly_consolidation_performed)
        self.assertEqual(week, "2025-W52")
        self.assertEqual(month, "2025-12")

    def test_session_start_rolls_back_all_maintenance_on_failure(self):
        with get_db() as db:
            db.execute(
                """
                CREATE TRIGGER fail_monthly_rollover
                BEFORE INSERT ON monthly_summaries
                BEGIN
                  SELECT RAISE(ABORT, 'forced rollover failure');
                END
                """
            )

        try:
            with patch("app.utc_now", return_value="2026-09-20T09:00:00+00:00"):
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "forced rollover failure",
                ):
                    start_session(StartSessionRequest())
        finally:
            with get_db() as db:
                db.execute("DROP TRIGGER IF EXISTS fail_monthly_rollover")

        with get_db() as db:
            session_count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            weekly_count = db.execute(
                "SELECT COUNT(*) FROM weekly_summaries"
            ).fetchone()[0]
            monthly_count = db.execute(
                "SELECT COUNT(*) FROM monthly_summaries"
            ).fetchone()[0]

        self.assertEqual(session_count, 0)
        self.assertEqual(weekly_count, 0)
        self.assertEqual(monthly_count, 0)


if __name__ == "__main__":
    unittest.main()
