import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "consolidation-test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from consolidation import consolidate_month, consolidate_week
from db import _migrate_existing_schema, get_db, init_db
from learning import record_grammar_event, record_vocabulary_event
from models import GrammarEventRequest, VocabularyEventRequest
from test_support import reset_learning_data


class ConsolidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db() as db:
            reset_learning_data(db)

    def create_session(self, started_at="2026-09-02T08:00:00+00:00"):
        with get_db() as db:
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('s1', ?, 'FRENCH', 'ENGLISH', 'MORNING_WALK')""",
                (started_at,),
            )

    def vocabulary(self, event_type, occurred_at, method=None):
        with get_db() as db:
            return record_vocabulary_event(
                db,
                VocabularyEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="pourtant",
                    event_type=event_type,
                    review_method=method,
                    occurred_at=occurred_at,
                ),
            )

    def grammar(self, event_type, occurred_at, method=None):
        with get_db() as db:
            return record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="depuis + present",
                    event_type=event_type,
                    review_method=method,
                    usefulness_score=5,
                    occurred_at=occurred_at,
                ),
            )

    def test_weekly_consolidation_is_per_item_archival_and_idempotent(self):
        self.create_session()
        self.vocabulary("MEANING_REQUEST", "2026-09-02T08:05:00+00:00")
        self.vocabulary(
            "FAILURE",
            "2026-09-03T08:05:00+00:00",
            method="ENGLISH_TO_FRENCH",
        )
        self.vocabulary(
            "SPONTANEOUS_SUCCESS",
            "2026-09-04T08:05:00+00:00",
            method="COVERT_CONVERSATION",
        )
        self.grammar(
            "LEARNING_ERROR",
            "2026-09-03T08:10:00+00:00",
            method="GRAMMAR_CORRECTION",
        )
        self.grammar(
            "CORRECT_USAGE",
            "2026-09-04T08:10:00+00:00",
            method="GRAMMAR_CORRECTION",
        )

        with get_db() as db:
            before = db.execute(
                """
                SELECT
                  (SELECT mistake_count_total FROM vocabulary_items) AS vocabulary_mistakes,
                  (SELECT mistake_count_total FROM grammar_items) AS grammar_mistakes,
                  (SELECT correct_usage_count FROM grammar_items) AS grammar_correct
                """
            ).fetchone()
            first = consolidate_week(
                db,
                "2026-W36",
                today=date(2026, 9, 20),
                consolidated_at="2026-09-20T10:00:00+00:00",
            )

        self.assertEqual(first.vocabulary_item_count, 1)
        self.assertEqual(first.grammar_item_count, 1)
        self.assertEqual(first.vocabulary_event_count, 3)
        self.assertEqual(first.grammar_event_count, 2)
        self.assertEqual(first.newly_archived_event_count, 5)

        with get_db() as db:
            vocabulary = db.execute(
                "SELECT * FROM weekly_vocabulary_summaries WHERE week = '2026-W36'"
            ).fetchone()
            grammar = db.execute(
                "SELECT * FROM weekly_grammar_summaries WHERE week = '2026-W36'"
            ).fetchone()
            global_summary = db.execute(
                "SELECT * FROM weekly_summaries WHERE week = '2026-W36'"
            ).fetchone()
            archived = db.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM vocabulary_events WHERE archived_at IS NOT NULL) +
                  (SELECT COUNT(*) FROM grammar_events WHERE archived_at IS NOT NULL)
                """
            ).fetchone()[0]

            statements = []
            db.set_trace_callback(statements.append)
            second = consolidate_week(
                db,
                "2026-W36",
                today=date(2026, 9, 20),
                consolidated_at="2026-09-20T11:00:00+00:00",
            )
            db.set_trace_callback(None)
            after = db.execute(
                """
                SELECT
                  (SELECT mistake_count_total FROM vocabulary_items) AS vocabulary_mistakes,
                  (SELECT mistake_count_total FROM grammar_items) AS grammar_mistakes,
                  (SELECT correct_usage_count FROM grammar_items) AS grammar_correct,
                  (SELECT COUNT(*) FROM weekly_vocabulary_summaries WHERE week = '2026-W36') AS vocabulary_summaries,
                  (SELECT COUNT(*) FROM weekly_grammar_summaries WHERE week = '2026-W36') AS grammar_summaries
                """
            ).fetchone()

        self.assertEqual(vocabulary["attempt_count"], 3)
        self.assertEqual(vocabulary["mistake_count"], 1)
        self.assertEqual(vocabulary["qualifying_spontaneous_success_count"], 1)
        self.assertEqual(vocabulary["most_used_review_method"], "COVERT_CONVERSATION")
        self.assertEqual(grammar["attempt_count"], 2)
        self.assertEqual(grammar["mistake_count"], 1)
        self.assertEqual(grammar["success_count"], 1)
        self.assertEqual(grammar["most_used_review_method"], "GRAMMAR_CORRECTION")
        self.assertEqual(global_summary["session_count"], 1)
        self.assertEqual(archived, 5)
        self.assertEqual(second.newly_archived_event_count, 0)
        self.assertEqual(second.consolidated_at, "2026-09-20T10:00:00+00:00")
        self.assertFalse(
            any(
                statement.lstrip().upper().startswith("SELECT")
                and (
                    "VOCABULARY_EVENTS" in statement.upper()
                    or "GRAMMAR_EVENTS" in statement.upper()
                )
                for statement in statements
            )
        )
        self.assertEqual(after["vocabulary_summaries"], 1)
        self.assertEqual(after["grammar_summaries"], 1)
        self.assertEqual(after["vocabulary_mistakes"], before["vocabulary_mistakes"])
        self.assertEqual(after["grammar_mistakes"], before["grammar_mistakes"])
        self.assertEqual(after["grammar_correct"], before["grammar_correct"])

    def test_monthly_consolidation_creates_per_item_summaries(self):
        self.create_session("2026-08-20T08:00:00+00:00")
        self.vocabulary("FAILURE", "2026-08-20T08:05:00+00:00")
        self.grammar("LEARNING_ERROR", "2026-08-20T08:10:00+00:00")

        with get_db() as db:
            result = consolidate_month(
                db,
                "2026-08",
                today=date(2026, 9, 20),
                consolidated_at="2026-09-20T10:00:00+00:00",
            )
            vocabulary_count = db.execute(
                "SELECT COUNT(*) FROM monthly_vocabulary_summaries WHERE month = '2026-08'"
            ).fetchone()[0]
            grammar_count = db.execute(
                "SELECT COUNT(*) FROM monthly_grammar_summaries WHERE month = '2026-08'"
            ).fetchone()[0]
            global_summary = db.execute(
                "SELECT * FROM monthly_summaries WHERE month = '2026-08'"
            ).fetchone()

        self.assertEqual(result.newly_archived_event_count, 2)
        self.assertEqual(vocabulary_count, 1)
        self.assertEqual(grammar_count, 1)
        self.assertEqual(global_summary["session_count"], 1)
        self.assertEqual(global_summary["vocabulary_mistakes_month"], 1)
        self.assertEqual(global_summary["grammar_mistakes_month"], 1)

    def test_operational_state_does_not_scan_archived_events(self):
        self.create_session()
        self.vocabulary("SPONTANEOUS_SUCCESS", "2026-09-02T08:05:00+00:00")
        for minute in range(5):
            stable = self.grammar(
                "SPONTANEOUS_SUCCESS",
                f"2026-09-02T08:{10 + minute:02d}:00+00:00",
            )
        self.assertEqual(stable.status, "STABLE")

        with get_db() as db:
            consolidate_week(
                db,
                "2026-W36",
                today=date(2026, 9, 20),
                consolidated_at="2026-09-20T10:00:00+00:00",
            )

        statements = []
        with get_db() as db:
            db.set_trace_callback(statements.append)
            learned = record_vocabulary_event(
                db,
                VocabularyEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="pourtant",
                    event_type="SPONTANEOUS_SUCCESS",
                    occurred_at="2026-09-09T08:05:00+00:00",
                ),
            )
            still_stable = record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="depuis + present",
                    event_type="SPONTANEOUS_SUCCESS",
                    usefulness_score=5,
                    occurred_at="2026-09-09T08:10:00+00:00",
                ),
            )
            db.set_trace_callback(None)

        event_selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and ("VOCABULARY_EVENTS" in statement.upper() or "GRAMMAR_EVENTS" in statement.upper())
        ]
        self.assertEqual(learned.status, "LEARNED")
        self.assertEqual(learned.qualifying_spontaneous_weeks, 2)
        self.assertEqual(still_stable.status, "STABLE")
        self.assertEqual(still_stable.recent_correct_count, 6)
        self.assertEqual(event_selects, [])

    def test_incomplete_periods_are_rejected(self):
        self.create_session()
        with get_db() as db:
            with self.assertRaisesRegex(ValueError, "completed periods"):
                consolidate_week(db, "2026-W38", today=date(2026, 9, 20))
            with self.assertRaisesRegex(ValueError, "completed periods"):
                consolidate_month(db, "2026-09", today=date(2026, 9, 20))

    def test_existing_v3_schema_is_migrated_in_place(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        try:
            db.executescript(
                """
                CREATE TABLE vocabulary_items (id INTEGER PRIMARY KEY);
                CREATE TABLE grammar_items (id INTEGER PRIMARY KEY);
                CREATE TABLE sessions (id TEXT PRIMARY KEY);
                CREATE TABLE vocabulary_events (id INTEGER PRIMARY KEY);
                CREATE TABLE grammar_events (id INTEGER PRIMARY KEY);
                """
            )
            added_columns = _migrate_existing_schema(db)
            no_columns_added = _migrate_existing_schema(db)

            vocabulary_item_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(vocabulary_items)")
            }
            grammar_item_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(grammar_items)")
            }
            vocabulary_event_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(vocabulary_events)")
            }
            grammar_event_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(grammar_events)")
            }
            session_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(sessions)")
            }
        finally:
            db.close()

        self.assertIn("qualifying_spontaneous_weeks_json", vocabulary_item_columns)
        self.assertIn("recent_outcomes_json", grammar_item_columns)
        self.assertIn("archived_at", vocabulary_event_columns)
        self.assertIn("agent_supplied_immediately_before", vocabulary_event_columns)
        self.assertIn("archived_at", grammar_event_columns)
        self.assertIn("vocabulary_event_count", session_columns)
        self.assertIn("grammar_event_count", session_columns)
        self.assertIn(
            ("vocabulary_items", "qualifying_spontaneous_weeks_json"),
            added_columns,
        )
        self.assertEqual(no_columns_added, set())

    def test_consolidation_rolls_back_as_one_transaction(self):
        self.create_session()
        self.vocabulary("FAILURE", "2026-09-02T08:05:00+00:00")
        self.grammar("LEARNING_ERROR", "2026-09-02T08:10:00+00:00")

        with get_db() as db:
            db.execute(
                """
                CREATE TEMP TRIGGER fail_grammar_summary
                BEFORE INSERT ON weekly_grammar_summaries
                BEGIN
                  SELECT RAISE(ABORT, 'forced consolidation failure');
                END
                """
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "forced consolidation failure"):
                consolidate_week(
                    db,
                    "2026-W36",
                    today=date(2026, 9, 20),
                    consolidated_at="2026-09-20T10:00:00+00:00",
                )
            vocabulary_summaries = db.execute(
                "SELECT COUNT(*) FROM weekly_vocabulary_summaries"
            ).fetchone()[0]
            archived_events = db.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM vocabulary_events WHERE archived_at IS NOT NULL) +
                  (SELECT COUNT(*) FROM grammar_events WHERE archived_at IS NOT NULL)
                """
            ).fetchone()[0]

        self.assertEqual(vocabulary_summaries, 0)
        self.assertEqual(archived_events, 0)


if __name__ == "__main__":
    unittest.main()
