import os
import tempfile
import unittest
from pathlib import Path

# Set DB path before importing application modules.
_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from db import get_db, init_db
from learning import record_vocabulary_event
from models import VocabularyEventRequest
from test_support import reset_learning_data


class VocabularyLearningTests(unittest.TestCase):
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

    def record(
        self,
        event_type,
        date,
        prompted=False,
        learning_question=False,
        supplied_before=False,
        hint_level=0,
    ):
        with get_db() as db:
            return record_vocabulary_event(db, VocabularyEventRequest(
                session_id="s1",
                language="FRENCH",
                key="pourtant",
                event_type=event_type,
                occurred_at=date,
                agent_prompted_target=prompted,
                agent_supplied_immediately_before=supplied_before,
                learning_question=learning_question,
                hint_level=hint_level,
            ))

    def test_unknown_word_is_learning_not_mistake(self):
        result = self.record("MEANING_REQUEST", "2026-09-01T08:10:00+00:00")
        self.assertEqual(result.status, "LEARNING")
        self.assertEqual(result.mastery_level, 1)
        self.assertEqual(result.mistake_count_total, 0)

    def test_two_successes_same_week_do_not_learn(self):
        self.record("MEANING_REQUEST", "2026-09-01T08:10:00+00:00")
        self.record("SPONTANEOUS_SUCCESS", "2026-09-02T08:10:00+00:00")
        result = self.record("SPONTANEOUS_SUCCESS", "2026-09-03T08:10:00+00:00")
        self.assertEqual(result.qualifying_spontaneous_weeks, 1)
        self.assertEqual(result.status, "LEARNING")

    def test_two_different_weeks_learn(self):
        self.record("MEANING_REQUEST", "2026-09-01T08:10:00+00:00")
        self.record("SPONTANEOUS_SUCCESS", "2026-09-02T08:10:00+00:00")
        result = self.record("SPONTANEOUS_SUCCESS", "2026-09-09T08:10:00+00:00")
        self.assertEqual(result.qualifying_spontaneous_weeks, 2)
        self.assertEqual(result.status, "LEARNED")
        self.assertGreaterEqual(result.mastery_level, 4)

    def test_prompted_success_does_not_qualify(self):
        self.record("MEANING_REQUEST", "2026-09-01T08:10:00+00:00")
        self.record("SPONTANEOUS_SUCCESS", "2026-09-02T08:10:00+00:00")
        result = self.record("SPONTANEOUS_SUCCESS", "2026-09-09T08:10:00+00:00", prompted=True)
        self.assertEqual(result.qualifying_spontaneous_weeks, 1)
        self.assertEqual(result.status, "LEARNING")

    def test_supplied_or_strongly_hinted_success_does_not_qualify(self):
        self.record("SPONTANEOUS_SUCCESS", "2026-09-02T08:10:00+00:00")
        supplied = self.record(
            "SPONTANEOUS_SUCCESS",
            "2026-09-09T08:10:00+00:00",
            supplied_before=True,
        )
        hinted = self.record(
            "SPONTANEOUS_SUCCESS",
            "2026-09-16T08:10:00+00:00",
            hint_level=2,
        )
        self.assertEqual(supplied.qualifying_spontaneous_weeks, 1)
        self.assertEqual(hinted.qualifying_spontaneous_weeks, 1)
        self.assertEqual(hinted.status, "LEARNING")

    def test_failure_after_learned_returns_to_learning(self):
        self.record("MEANING_REQUEST", "2026-09-01T08:10:00+00:00")
        self.record("SPONTANEOUS_SUCCESS", "2026-09-02T08:10:00+00:00")
        learned = self.record("SPONTANEOUS_SUCCESS", "2026-09-09T08:10:00+00:00")
        self.assertEqual(learned.status, "LEARNED")
        result = self.record("FAILURE", "2026-09-16T08:10:00+00:00")
        self.assertEqual(result.status, "LEARNING")
        self.assertEqual(result.mistake_count_total, 1)


if __name__ == "__main__":
    unittest.main()
