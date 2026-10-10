import sqlite3


def reset_learning_data(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM weekly_vocabulary_summaries")
    db.execute("DELETE FROM weekly_grammar_summaries")
    db.execute("DELETE FROM monthly_vocabulary_summaries")
    db.execute("DELETE FROM monthly_grammar_summaries")
    db.execute("DELETE FROM weekly_summaries")
    db.execute("DELETE FROM monthly_summaries")
    db.execute("DELETE FROM grammar_events")
    db.execute("DELETE FROM vocabulary_events")
    db.execute("DELETE FROM grammar_items")
    db.execute("DELETE FROM vocabulary_items")
    db.execute("DELETE FROM sessions")
    db.execute(
        """
        UPDATE learner_profile
        SET baseline_date = NULL,
            baseline_french_cefr = NULL,
            overall_french_cefr = NULL,
            speaking_cefr = NULL,
            grammar_cefr = NULL,
            vocabulary_cefr = NULL,
            listening_cefr = NULL,
            fluency_cefr = NULL,
            strengths_json = NULL,
            weaknesses_json = NULL,
            best_learning_methods_json = NULL,
            weak_learning_methods_json = NULL,
            baseline_json = NULL
        WHERE id = 1
        """
    )
