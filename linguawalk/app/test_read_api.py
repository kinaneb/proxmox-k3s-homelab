import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ["LINGUAWALK_DB_PATH"] = str(Path(_tmp.name) / "read-api-test.db")
os.environ["LINGUAWALK_API_KEY"] = "test-key"

from app import app
from consolidation import consolidate_month, consolidate_week
from db import get_db, init_db
from learning import (
    end_session,
    load_learning_progress,
    load_learner_profile,
    record_grammar_event,
    record_vocabulary_event,
)
from models import EndSessionRequest, GrammarEventRequest, VocabularyEventRequest
from test_support import reset_learning_data


class ReadApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db() as db:
            reset_learning_data(db)
            db.execute(
                """
                UPDATE learner_profile
                SET baseline_date = '2026-09-01',
                    baseline_french_cefr = 'B1',
                    overall_french_cefr = 'B1',
                    speaking_cefr = 'B1',
                    grammar_cefr = 'A2',
                    vocabulary_cefr = 'B1',
                    listening_cefr = 'B1',
                    fluency_cefr = 'A2',
                    strengths_json = ?,
                    weaknesses_json = ?,
                    best_learning_methods_json = ?,
                    weak_learning_methods_json = ?,
                    baseline_json = ?
                WHERE id = 1
                """,
                (
                    json.dumps(["listening"]),
                    json.dumps(["agreement"]),
                    json.dumps(["COVERT_CONVERSATION"]),
                    json.dumps(["EXPLICIT_EXPLANATION"]),
                    json.dumps({"sample_minutes": 60, "source": "initial_walk"}),
                ),
            )
            db.execute(
                """INSERT INTO sessions
                   (id, started_at, primary_language, secondary_language, session_type)
                   VALUES ('s1', '2026-09-02T08:00:00+00:00',
                           'FRENCH', 'ENGLISH', 'MORNING_WALK')"""
            )
            record_vocabulary_event(
                db,
                VocabularyEventRequest(
                    session_id="s1",
                    language="FRENCH",
                    key="pourtant",
                    event_type="FAILURE",
                    occurred_at="2026-09-02T08:05:00+00:00",
                ),
            )
            record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    key="depuis present",
                    event_type="LEARNING_ERROR",
                    usefulness_score=5,
                    occurred_at="2026-09-02T08:10:00+00:00",
                ),
            )
            record_grammar_event(
                db,
                GrammarEventRequest(
                    session_id="s1",
                    key="depuis present",
                    event_type="CORRECT_USAGE",
                    usefulness_score=5,
                    occurred_at="2026-09-03T08:10:00+00:00",
                ),
            )
            end_session(db, EndSessionRequest(session_id="s1"))
            consolidate_week(
                db,
                "2026-W36",
                today=date(2026, 10, 5),
                consolidated_at="2026-10-05T08:00:00+00:00",
            )
            consolidate_month(
                db,
                "2026-09",
                today=date(2026, 10, 5),
                consolidated_at="2026-10-05T08:00:00+00:00",
            )

    def test_profile_exposes_baseline_preferences_and_current_counts(self):
        with get_db() as db:
            profile = load_learner_profile(db)

        self.assertEqual(profile.baseline_date, "2026-09-01")
        self.assertEqual(profile.baseline_french_cefr, "B1")
        self.assertEqual(profile.strengths, ["listening"])
        self.assertEqual(profile.weaknesses, ["agreement"])
        self.assertEqual(profile.best_learning_methods, ["COVERT_CONVERSATION"])
        self.assertEqual(profile.weak_learning_methods, ["EXPLICIT_EXPLANATION"])
        self.assertEqual(profile.baseline["sample_minutes"], 60)
        self.assertEqual(profile.active_vocabulary_count, 1)
        self.assertEqual(profile.active_grammar_count, 1)

    def test_progress_combines_lifetime_state_and_latest_summaries(self):
        with get_db() as db:
            progress = load_learning_progress(
                db,
                generated_at="2026-10-05T09:00:00+00:00",
            )

        self.assertEqual(progress.total_sessions, 1)
        self.assertEqual(progress.completed_sessions, 1)
        self.assertEqual(progress.vocabulary_event_count, 1)
        self.assertEqual(progress.grammar_event_count, 2)
        self.assertEqual(progress.vocabulary_learning, 1)
        self.assertEqual(progress.vocabulary_mistakes_total, 1)
        self.assertEqual(progress.grammar_active, 1)
        self.assertEqual(progress.grammar_mistakes_total, 1)
        self.assertEqual(progress.grammar_correct_usage_total, 1)
        self.assertEqual(progress.latest_weekly_summary.week, "2026-W36")
        self.assertEqual(progress.latest_weekly_summary.session_count, 1)
        self.assertEqual(progress.latest_monthly_summary.month, "2026-09")
        self.assertEqual(progress.latest_monthly_summary.vocabulary_mistakes, 1)

    def test_profile_and_progress_do_not_read_raw_event_tables(self):
        statements = []
        with get_db() as db:
            db.set_trace_callback(statements.append)
            load_learner_profile(db)
            load_learning_progress(db)
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
        self.assertEqual(event_selects, [])

    def test_openapi_exposes_all_authenticated_read_routes(self):
        schema = app.openapi()
        for path in ("/profile", "/progress", "/learning/targets"):
            self.assertIn(path, schema["paths"])
            parameters = schema["paths"][path]["get"]["parameters"]
            self.assertTrue(
                any(
                    parameter["name"] == "authorization"
                    and parameter["in"] == "header"
                    for parameter in parameters
                )
            )


if __name__ == "__main__":
    unittest.main()
