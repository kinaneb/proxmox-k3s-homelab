import os
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "grammar-test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from db import get_db, init_db
from learning import record_grammar_event
from models import GrammarEventRequest
from test_support import reset_learning_data


class GrammarLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db() as db:
            reset_learning_data(db)
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('s1', '2026-09-01T08:00:00+00:00', 'FRENCH', 'ENGLISH', 'MORNING_WALK')"""
            )

    def record(self, event_type, usefulness=5, date="2026-09-01T08:10:00+00:00"):
        with get_db() as db:
            return record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="depuis + present",
                    event_type=event_type,
                    usefulness_score=usefulness,
                    display_name="depuis + présent",
                    occurred_at=date,
                ),
            )

    def test_mistake_increments_and_priority(self):
        result = self.record("LEARNING_ERROR", usefulness=5)
        self.assertEqual(result.mistake_count_total, 1)
        self.assertEqual(result.status, "ACTIVE")
        self.assertAlmostEqual(result.priority_score, 5.0)

    def test_correct_usage_increments(self):
        self.record("LEARNING_ERROR")
        result = self.record("CORRECT_USAGE")
        self.assertEqual(result.correct_usage_count, 1)
        self.assertEqual(result.mistake_count_total, 1)
        self.assertAlmostEqual(result.error_rate, 0.5)

    def test_improving(self):
        self.record("LEARNING_ERROR")
        self.record("CORRECT_USAGE")
        self.record("CORRECT_USAGE")
        result = self.record("CORRECT_USAGE")
        self.assertEqual(result.status, "IMPROVING")

    def test_stable(self):
        for _ in range(5):
            result = self.record("SPONTANEOUS_SUCCESS")
        self.assertEqual(result.status, "STABLE")

    def test_fresh_failure_reactivates_stable_item(self):
        for _ in range(5):
            self.record("SPONTANEOUS_SUCCESS")
        result = self.record("RECURRING_ERROR")
        self.assertEqual(result.status, "ACTIVE")
        self.assertGreater(result.priority_score, 0.0)

    def test_usefulness_weights_priority(self):
        high = self.record("LEARNING_ERROR", usefulness=5)
        with get_db() as db:
            low = record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="rare literary structure",
                    event_type="LEARNING_ERROR",
                    usefulness_score=1,
                    occurred_at="2026-09-01T08:20:00+00:00",
                ),
            )
        self.assertGreater(high.priority_score, low.priority_score)


if __name__ == "__main__":
    unittest.main()
