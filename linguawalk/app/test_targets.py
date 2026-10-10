import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "targets-test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from db import get_db, init_db
from app import start_session
from learning import (
    get_learning_targets,
    record_grammar_event,
    record_vocabulary_event,
)
from models import GrammarEventRequest, StartSessionRequest, VocabularyEventRequest
from test_support import reset_learning_data


class HiddenTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db() as db:
            reset_learning_data(db)
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('s1', '2026-08-01T08:00:00+00:00',
                           'FRENCH', 'ENGLISH', 'MORNING_WALK')"""
            )

    def vocabulary(self, key, event_type, occurred_at):
        with get_db() as db:
            return record_vocabulary_event(
                db,
                VocabularyEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key=key,
                    event_type=event_type,
                    occurred_at=occurred_at,
                ),
            )

    def grammar(self, key, event_type, occurred_at, usefulness):
        with get_db() as db:
            return record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    key=key,
                    event_type=event_type,
                    usefulness_score=usefulness,
                    occurred_at=occurred_at,
                ),
            )

    def test_vocabulary_targets_follow_reactivation_schedule(self):
        self.vocabulary("recent failure", "FAILURE", "2026-09-19T08:00:00+00:00")
        self.vocabulary("not due", "MEANING_REQUEST", "2026-09-19T08:00:00+00:00")
        self.vocabulary("assisted", "NATURAL_SUCCESS", "2026-09-10T08:00:00+00:00")
        self.vocabulary("independent", "NATURAL_SUCCESS", "2026-09-05T08:00:00+00:00")
        self.vocabulary("stable", "NATURAL_SUCCESS", "2026-08-20T08:00:00+00:00")

        with get_db() as db:
            db.execute(
                """UPDATE vocabulary_items
                   SET status = 'LEARNED', mastery_level = 4
                   WHERE normalized_key = 'independent'"""
            )
            db.execute(
                """UPDATE vocabulary_items
                   SET status = 'LEARNED', mastery_level = 5
                   WHERE normalized_key = 'stable'"""
            )
            targets = get_learning_targets(
                db,
                as_of="2026-09-20T09:00:00+00:00",
            ).vocabulary

        by_key = {target.key: target for target in targets}
        self.assertEqual(targets[0].key, "recent failure")
        self.assertNotIn("not due", by_key)
        self.assertIn("Current-week failure", by_key["recent failure"].reason)
        self.assertEqual(
            by_key["recent failure"].next_review_at,
            "2026-09-21T08:00:00+00:00",
        )
        self.assertEqual(
            by_key["recent failure"].recommended_method,
            "ENGLISH_TO_FRENCH",
        )
        self.assertIn("D+7", by_key["assisted"].reason)
        self.assertEqual(by_key["assisted"].recommended_method, "SENTENCE_CREATION")
        self.assertIn("D+14", by_key["independent"].reason)
        self.assertIn("D+30", by_key["stable"].reason)
        self.assertEqual(by_key["stable"].recommended_method, "COVERT_CONVERSATION")

    def test_grammar_targets_rank_usefulness_and_current_weakness(self):
        high = self.grammar(
            "common structure",
            "LEARNING_ERROR",
            "2026-09-19T08:00:00+00:00",
            5,
        )
        low = self.grammar(
            "rare structure",
            "LEARNING_ERROR",
            "2026-09-19T08:00:00+00:00",
            1,
        )
        for _ in range(5):
            self.grammar(
                "stable structure",
                "SPONTANEOUS_SUCCESS",
                "2026-08-15T08:00:00+00:00",
                4,
            )

        with get_db() as db:
            targets = get_learning_targets(
                db,
                as_of="2026-09-20T09:00:00+00:00",
            ).grammar

        by_key = {target.key: target for target in targets}
        self.assertEqual(high.priority_score, 5.0)
        self.assertEqual(low.priority_score, 1.0)
        self.assertEqual(targets[0].key, "common_structure")
        self.assertEqual(by_key["common_structure"].priority_score, 5.0)
        self.assertEqual(
            by_key["common_structure"].recommended_method,
            "GRAMMAR_CORRECTION",
        )
        self.assertIn("D+30", by_key["stable_structure"].reason)
        self.assertEqual(
            by_key["stable_structure"].recommended_method,
            "COVERT_CONVERSATION",
        )

    def test_target_selection_does_not_read_event_tables(self):
        self.vocabulary("pourtant", "FAILURE", "2026-09-10T08:00:00+00:00")
        self.grammar(
            "depuis present",
            "LEARNING_ERROR",
            "2026-09-10T08:00:00+00:00",
            5,
        )

        statements = []
        with get_db() as db:
            db.set_trace_callback(statements.append)
            targets = get_learning_targets(
                db,
                as_of="2026-09-20T09:00:00+00:00",
            )
            db.set_trace_callback(None)

        event_selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and (
                "VOCABULARY_EVENTS" in statement.upper()
                or "GRAMMAR_EVENTS" in statement.upper()
            )
        ]
        self.assertEqual(len(targets.vocabulary), 1)
        self.assertEqual(len(targets.grammar), 1)
        self.assertEqual(event_selects, [])

    def test_session_start_returns_hidden_scheduled_targets(self):
        self.vocabulary("pourtant", "FAILURE", "2026-09-19T08:00:00+00:00")
        self.grammar(
            "depuis present",
            "LEARNING_ERROR",
            "2026-09-19T08:05:00+00:00",
            5,
        )

        with patch("app.utc_now", return_value="2026-09-20T09:00:00+00:00"):
            response = start_session(StartSessionRequest())

        self.assertEqual(response.targets.vocabulary[0].key, "pourtant")
        self.assertEqual(
            response.targets.vocabulary[0].recommended_method,
            "ENGLISH_TO_FRENCH",
        )
        self.assertEqual(response.targets.grammar[0].key, "depuis_present")
        self.assertEqual(
            response.targets.grammar[0].recommended_method,
            "GRAMMAR_CORRECTION",
        )


if __name__ == "__main__":
    unittest.main()
