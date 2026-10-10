import json
import os
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "session-test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from db import get_db, init_db
from learning import end_session, record_grammar_event, record_vocabulary_event
from models import (
    EndSessionRequest,
    GrammarEventRequest,
    VocabularyEventRequest,
)
from test_support import reset_learning_data


class SessionEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db() as db:
            reset_learning_data(db)
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('s1', '2026-09-20T08:00:00+00:00', 'FRENCH', 'ENGLISH', 'MORNING_WALK')"""
            )

    def test_end_session_persists_summary_and_event_counts(self):
        with get_db() as db:
            record_vocabulary_event(
                db,
                VocabularyEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="pourtant",
                    event_type="MEANING_REQUEST",
                ),
            )
            record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    key="depuis + present",
                    event_type="LEARNING_ERROR",
                ),
            )
            result = end_session(
                db,
                EndSessionRequest(
                    session_id="s1",
                    subjects=[" Daily news ", "travel", "daily NEWS", "  "],
                    summary="  Discussed transport policy.  ",
                    learner_notes="  Review depuis next time.  ",
                ),
            )

            row = db.execute("SELECT * FROM sessions WHERE id = 's1'").fetchone()

        self.assertFalse(result.already_ended)
        self.assertEqual(result.subjects, ["Daily news", "travel"])
        self.assertEqual(result.summary, "Discussed transport policy.")
        self.assertEqual(result.learner_notes, "Review depuis next time.")
        self.assertEqual(result.vocabulary_event_count, 1)
        self.assertEqual(result.grammar_event_count, 1)
        self.assertEqual(result.total_event_count, 2)
        self.assertIsNotNone(result.ended_at)
        self.assertEqual(json.loads(row["subjects_json"]), result.subjects)

    def test_end_session_retry_preserves_first_close(self):
        with get_db() as db:
            first = end_session(
                db,
                EndSessionRequest(
                    session_id="s1",
                    subjects=["news"],
                    summary="First summary",
                    learner_notes="First notes",
                ),
            )
            retry = end_session(
                db,
                EndSessionRequest(
                    session_id="s1",
                    subjects=["replacement"],
                    summary="Replacement summary",
                    learner_notes="Replacement notes",
                ),
            )

        self.assertTrue(retry.already_ended)
        self.assertEqual(retry.ended_at, first.ended_at)
        self.assertEqual(retry.subjects, ["news"])
        self.assertEqual(retry.summary, "First summary")
        self.assertEqual(retry.learner_notes, "First notes")

    def test_end_unknown_session_fails(self):
        with get_db() as db:
            with self.assertRaisesRegex(ValueError, "Unknown session_id"):
                end_session(db, EndSessionRequest(session_id="missing"))


if __name__ == "__main__":
    unittest.main()
