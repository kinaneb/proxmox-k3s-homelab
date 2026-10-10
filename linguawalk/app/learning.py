import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

from db import utc_now
from models import (
    EndSessionRequest,
    EndSessionResult,
    GrammarEventRequest,
    GrammarEventResult,
    GrammarTarget,
    LearnerProfile,
    LearningProgress,
    LearningTargets,
    MonthlyProgressSummary,
    VocabularyEventRequest,
    VocabularyEventResult,
    VocabularyTarget,
    WeeklyProgressSummary,
)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _json_object(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def load_learner_profile(db: sqlite3.Connection) -> LearnerProfile:
    profile = db.execute("SELECT * FROM learner_profile WHERE id = 1").fetchone()
    counts = db.execute("""
        SELECT
          (SELECT COUNT(*) FROM vocabulary_items WHERE status != 'LEARNED') AS active_vocabulary_count,
          (SELECT COUNT(*) FROM vocabulary_items WHERE status = 'LEARNED') AS learned_vocabulary_count,
          (SELECT COUNT(*) FROM grammar_items WHERE status IN ('ACTIVE','IMPROVING')) AS active_grammar_count,
          (SELECT COUNT(*) FROM grammar_items WHERE status = 'STABLE') AS stable_grammar_count
    """).fetchone()

    return LearnerProfile(
        baseline_date=profile["baseline_date"],
        baseline_french_cefr=profile["baseline_french_cefr"],
        overall_french_cefr=profile["overall_french_cefr"],
        speaking_cefr=profile["speaking_cefr"],
        grammar_cefr=profile["grammar_cefr"],
        vocabulary_cefr=profile["vocabulary_cefr"],
        listening_cefr=profile["listening_cefr"],
        fluency_cefr=profile["fluency_cefr"],
        strengths=_json_list(profile["strengths_json"]),
        weaknesses=_json_list(profile["weaknesses_json"]),
        best_learning_methods=_json_list(profile["best_learning_methods_json"]),
        weak_learning_methods=_json_list(profile["weak_learning_methods_json"]),
        baseline=_json_object(profile["baseline_json"]),
        active_vocabulary_count=counts["active_vocabulary_count"],
        learned_vocabulary_count=counts["learned_vocabulary_count"],
        active_grammar_count=counts["active_grammar_count"],
        stable_grammar_count=counts["stable_grammar_count"],
    )


def load_learning_progress(
    db: sqlite3.Connection,
    *,
    generated_at: str | None = None,
) -> LearningProgress:
    sessions = db.execute(
        """
        SELECT
          COUNT(*) AS total_sessions,
          COALESCE(SUM(CASE WHEN ended_at IS NOT NULL THEN 1 ELSE 0 END), 0)
            AS completed_sessions,
          COALESCE(SUM(vocabulary_event_count), 0) AS vocabulary_event_count,
          COALESCE(SUM(grammar_event_count), 0) AS grammar_event_count
        FROM sessions
        """
    ).fetchone()
    vocabulary = db.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN status = 'NOT_LEARNED' THEN 1 ELSE 0 END), 0)
            AS not_learned,
          COALESCE(SUM(CASE WHEN status = 'LEARNING' THEN 1 ELSE 0 END), 0)
            AS learning,
          COALESCE(SUM(CASE WHEN status = 'LEARNED' THEN 1 ELSE 0 END), 0)
            AS learned,
          COALESCE(SUM(mistake_count_total), 0) AS mistakes
        FROM vocabulary_items
        """
    ).fetchone()
    grammar = db.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END), 0)
            AS active,
          COALESCE(SUM(CASE WHEN status = 'IMPROVING' THEN 1 ELSE 0 END), 0)
            AS improving,
          COALESCE(SUM(CASE WHEN status = 'STABLE' THEN 1 ELSE 0 END), 0)
            AS stable,
          COALESCE(SUM(mistake_count_total), 0) AS mistakes,
          COALESCE(SUM(correct_usage_count), 0) AS correct_usage
        FROM grammar_items
        """
    ).fetchone()
    weekly = db.execute(
        "SELECT * FROM weekly_summaries ORDER BY week DESC LIMIT 1"
    ).fetchone()
    monthly = db.execute(
        "SELECT * FROM monthly_summaries ORDER BY month DESC LIMIT 1"
    ).fetchone()

    weekly_summary = None
    if weekly is not None:
        weekly_summary = WeeklyProgressSummary(
            week=weekly["week"],
            start_date=weekly["start_date"],
            end_date=weekly["end_date"],
            session_count=weekly["session_count"],
            vocabulary_learning=weekly["vocabulary_learning"],
            vocabulary_learned=weekly["vocabulary_learned"],
            vocabulary_mistakes=weekly["vocabulary_mistakes"],
            active_grammar=weekly["active_grammar"],
            improving_grammar=weekly["improving_grammar"],
            stable_grammar=weekly["stable_grammar"],
            grammar_mistakes=weekly["grammar_mistakes"],
            consolidated_at=weekly["created_at"],
        )

    monthly_summary = None
    if monthly is not None:
        monthly_summary = MonthlyProgressSummary(
            month=monthly["month"],
            session_count=monthly["session_count"],
            vocabulary_learning=monthly["vocabulary_learning"],
            vocabulary_learned=monthly["vocabulary_learned"],
            vocabulary_mistakes=monthly["vocabulary_mistakes_month"],
            active_grammar=monthly["active_grammar"],
            improving_grammar=monthly["improving_grammar"],
            stable_grammar=monthly["stable_grammar"],
            grammar_mistakes=monthly["grammar_mistakes_month"],
            french_cefr=monthly["french_cefr"],
            consolidated_at=monthly["created_at"],
        )

    return LearningProgress(
        generated_at=generated_at or utc_now(),
        total_sessions=sessions["total_sessions"],
        completed_sessions=sessions["completed_sessions"],
        vocabulary_event_count=sessions["vocabulary_event_count"],
        grammar_event_count=sessions["grammar_event_count"],
        vocabulary_not_learned=vocabulary["not_learned"],
        vocabulary_learning=vocabulary["learning"],
        vocabulary_learned=vocabulary["learned"],
        vocabulary_mistakes_total=vocabulary["mistakes"],
        grammar_active=grammar["active"],
        grammar_improving=grammar["improving"],
        grammar_stable=grammar["stable"],
        grammar_mistakes_total=grammar["mistakes"],
        grammar_correct_usage_total=grammar["correct_usage"],
        latest_weekly_summary=weekly_summary,
        latest_monthly_summary=monthly_summary,
    )


def _utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_datetime(*values: str | None) -> datetime | None:
    parsed = [_utc_datetime(value) for value in values if value]
    return max(parsed) if parsed else None


def _same_iso_week(left: datetime, right: datetime) -> bool:
    return left.date().isocalendar()[:2] == right.date().isocalendar()[:2]


def _reactivation_label(reference: datetime, as_of: datetime) -> str:
    age_days = max(0, (as_of.date() - reference.date()).days)
    if age_days >= 30:
        return "D+30"
    if age_days >= 14:
        return "D+14"
    if age_days >= 7:
        return "D+7"
    return "D+2"


def _vocabulary_schedule(row: sqlite3.Row) -> tuple[datetime, datetime, bool]:
    last_mistake = _latest_datetime(row["last_mistake_at"])
    last_success = _latest_datetime(row["last_success_at"])
    reference = _latest_datetime(
        row["last_mistake_at"],
        row["last_success_at"],
        row["first_seen_at"],
    )
    unresolved_failure = (
        last_mistake is not None
        and (last_success is None or last_mistake >= last_success)
    )
    if unresolved_failure or row["mastery_level"] <= 2:
        interval_days = 2
    elif row["mastery_level"] == 3:
        interval_days = 7
    elif row["mastery_level"] == 4:
        interval_days = 14
    else:
        interval_days = 30
    return reference, reference + timedelta(days=interval_days), unresolved_failure


def _grammar_schedule(row: sqlite3.Row) -> tuple[datetime, datetime, bool]:
    last_mistake = _latest_datetime(row["last_mistake_at"])
    last_success = _latest_datetime(row["last_success_at"])
    reference = _latest_datetime(
        row["last_mistake_at"],
        row["last_success_at"],
        row["first_seen_at"],
    )
    unresolved_failure = (
        last_mistake is not None
        and (last_success is None or last_mistake >= last_success)
    )
    if unresolved_failure or row["status"] == "ACTIVE":
        interval_days = 2
    elif row["status"] == "IMPROVING" and row["correct_usage_count"] < 4:
        interval_days = 7
    elif row["status"] == "IMPROVING":
        interval_days = 14
    else:
        interval_days = 30
    return reference, reference + timedelta(days=interval_days), unresolved_failure


def _vocabulary_method(row: sqlite3.Row, unresolved_failure: bool) -> str:
    if unresolved_failure:
        return "ENGLISH_TO_FRENCH"
    if row["mastery_level"] <= 1:
        return "FRENCH_TO_ENGLISH"
    if row["mastery_level"] == 2:
        return "ENGLISH_TO_FRENCH"
    if row["mastery_level"] == 3:
        return "SENTENCE_CREATION"
    return "COVERT_CONVERSATION"


def _grammar_method(row: sqlite3.Row) -> str:
    if row["status"] == "ACTIVE":
        return "GRAMMAR_CORRECTION"
    if row["status"] == "IMPROVING":
        return "SENTENCE_CREATION"
    return "COVERT_CONVERSATION"


def get_learning_targets(
    db: sqlite3.Connection,
    vocabulary_limit: int = 6,
    grammar_limit: int = 6,
    *,
    as_of: str | None = None,
) -> LearningTargets:
    now = _utc_datetime(as_of) if as_of else datetime.now(timezone.utc)
    vocabulary_candidates = []
    for row in db.execute("SELECT * FROM vocabulary_items"):
        reference, next_review, unresolved_failure = _vocabulary_schedule(row)
        current_week_failure = (
            row["last_mistake_at"] is not None
            and _same_iso_week(_utc_datetime(row["last_mistake_at"]), now)
        )
        if next_review > now and not current_week_failure:
            continue
        age_label = _reactivation_label(reference, now)
        priority = (
            (100 if current_week_failure else 0)
            + 50
            + {"D+2": 5, "D+7": 10, "D+14": 15, "D+30": 20}[age_label]
            + {"NOT_LEARNED": 20, "LEARNING": 25, "LEARNED": 5}[row["status"]]
            + row["difficulty"] * 4
            + (6 - row["mastery_level"]) * 3
            + min(row["mistake_count_total"], 10) * 2
        )
        reason_prefix = "Current-week failure" if current_week_failure else age_label
        target = VocabularyTarget(
            key=row["key"],
            language=row["language"],
            status=row["status"],
            mastery_level=row["mastery_level"],
            difficulty=row["difficulty"],
            priority=float(priority),
            last_seen=row["last_seen_at"],
            last_mistake=row["last_mistake_at"],
            next_review_at=next_review.isoformat(),
            recommended_method=_vocabulary_method(row, unresolved_failure),
            reason=(
                f"{reason_prefix} vocabulary reactivation; "
                f"status {row['status']}, mastery {row['mastery_level']}, "
                f"difficulty {row['difficulty']}."
            ),
        )
        vocabulary_candidates.append((priority, reference, row["key"], target))

    grammar_candidates = []
    for row in db.execute("SELECT * FROM grammar_items"):
        reference, next_review, _ = _grammar_schedule(row)
        current_week_failure = (
            row["last_mistake_at"] is not None
            and _same_iso_week(_utc_datetime(row["last_mistake_at"]), now)
        )
        if next_review > now and not current_week_failure:
            continue
        age_label = _reactivation_label(reference, now)
        priority = (
            (100 if current_week_failure else 0)
            + 50
            + {"D+2": 5, "D+7": 10, "D+14": 15, "D+30": 20}[age_label]
            + {"ACTIVE": 25, "IMPROVING": 15, "STABLE": 5}[row["status"]]
            + row["usefulness_score"] * 4
            + row["priority_score"] * 10
            + min(row["mistake_count_total"], 10) * 2
        )
        reason_prefix = "Current-week failure" if current_week_failure else age_label
        target = GrammarTarget(
            key=row["key"],
            display_name=row["display_name"],
            usefulness_score=row["usefulness_score"],
            correct_usage_count=row["correct_usage_count"],
            mistake_count=row["mistake_count_total"],
            error_rate=row["error_rate"],
            priority_score=row["priority_score"],
            status=row["status"],
            last_mistake=row["last_mistake_at"],
            last_success=row["last_success_at"],
            next_review_at=next_review.isoformat(),
            recommended_method=_grammar_method(row),
            reason=(
                f"{reason_prefix} grammar reactivation; status {row['status']}, "
                f"usefulness {row['usefulness_score']}, current weakness "
                f"{row['priority_score']:.2f}."
            ),
        )
        grammar_candidates.append((priority, reference, row["key"], target))

    vocabulary_candidates.sort(
        key=lambda candidate: (-candidate[0], candidate[1], candidate[2])
    )
    grammar_candidates.sort(
        key=lambda candidate: (-candidate[0], candidate[1], candidate[2])
    )
    return LearningTargets(
        vocabulary=[candidate[3] for candidate in vocabulary_candidates[:vocabulary_limit]],
        grammar=[candidate[3] for candidate in grammar_candidates[:grammar_limit]],
    )


def _normalize_subjects(subjects: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for subject in subjects:
        value = " ".join(subject.split())
        deduplication_key = value.casefold()
        if value and deduplication_key not in seen:
            normalized.append(value)
            seen.add(deduplication_key)
    return normalized


def _normalized_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def end_session(db: sqlite3.Connection, request: EndSessionRequest) -> EndSessionResult:
    session = db.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (request.session_id,),
    ).fetchone()
    if session is None:
        raise ValueError("Unknown session_id")

    already_ended = session["ended_at"] is not None
    if not already_ended:
        ended_at = utc_now()
        db.execute(
            """
            UPDATE sessions
            SET ended_at = ?, subjects_json = ?, summary = ?, learner_notes = ?
            WHERE id = ?
            """,
            (
                ended_at,
                json.dumps(_normalize_subjects(request.subjects), ensure_ascii=False),
                _normalized_optional_text(request.summary),
                _normalized_optional_text(request.learner_notes),
                request.session_id,
            ),
        )

    session = db.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (request.session_id,),
    ).fetchone()
    vocabulary_event_count = session["vocabulary_event_count"]
    grammar_event_count = session["grammar_event_count"]
    return EndSessionResult(
        success=True,
        session_id=session["id"],
        started_at=session["started_at"],
        ended_at=session["ended_at"],
        already_ended=already_ended,
        subjects=_json_list(session["subjects_json"]),
        summary=session["summary"],
        learner_notes=session["learner_notes"],
        vocabulary_event_count=vocabulary_event_count,
        grammar_event_count=grammar_event_count,
        total_event_count=vocabulary_event_count + grammar_event_count,
    )



def normalize_vocabulary_key(key: str) -> str:
    # Preserve accents because they can distinguish words, but normalize Unicode,
    # whitespace, surrounding punctuation, and case.
    value = unicodedata.normalize("NFC", key).strip().casefold()
    value = re.sub(r"^[\\s\\\"'“”‘’.,;:!?()\\[\\]{}]+|[\\s\\\"'“”‘’.,;:!?()\\[\\]{}]+$", "", value)
    value = re.sub(r"\\s+", " ", value)
    return value


def _parse_event_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _calendar_week(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def record_vocabulary_event(db: sqlite3.Connection, event: VocabularyEventRequest) -> VocabularyEventResult:
    # Validate session exists.
    session = db.execute("SELECT id FROM sessions WHERE id = ?", (event.session_id,)).fetchone()
    if session is None:
        raise ValueError("Unknown session_id")

    normalized = normalize_vocabulary_key(event.key)
    if not normalized:
        raise ValueError("Vocabulary key cannot be empty")

    dt = _parse_event_time(event.occurred_at)
    occurred_at = dt.isoformat()
    week = _calendar_week(dt)

    item = db.execute(
        "SELECT * FROM vocabulary_items WHERE language = ? AND normalized_key = ?",
        (event.language, normalized),
    ).fetchone()

    if item is None:
        # Any explicit unknown/meaning/spelling event creates a learning item.
        initial_status = "LEARNING"
        initial_mastery = 1
        db.execute(
            """
            INSERT INTO vocabulary_items (
                language, key, normalized_key, meaning, status, mastery_level,
                difficulty, mistake_count_total, spontaneous_success_count,
                first_seen_at, last_seen_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, ?, ?, ?, ?)
            """,
            (
                event.language, event.key.strip(), normalized, event.meaning,
                initial_status, initial_mastery,
                occurred_at, occurred_at, occurred_at, occurred_at,
            ),
        )
        item_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        item_id = item["id"]

    db.execute(
        """
        INSERT INTO vocabulary_events (
            session_id, vocabulary_item_id, created_at, event_type,
            session_subject, event_subject, user_form, correct_form,
            meaning, example, review_method, hint_level, retrieval_speed,
            agent_prompted_target, agent_supplied_immediately_before,
            learning_question, calendar_week, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.session_id, item_id, occurred_at, event.event_type,
            event.session_subject, event.event_subject, event.user_form,
            event.correct_form, event.meaning, event.example, event.review_method,
            event.hint_level, event.retrieval_speed,
            int(event.agent_prompted_target),
            int(event.agent_supplied_immediately_before),
            int(event.learning_question),
            week, event.notes,
        ),
    )
    db.execute(
        """
        UPDATE sessions
        SET vocabulary_event_count = vocabulary_event_count + 1
        WHERE id = ?
        """,
        (event.session_id,),
    )

    # Update factual item fields first.
    if event.meaning:
        db.execute("UPDATE vocabulary_items SET meaning = ? WHERE id = ?", (event.meaning, item_id))

    if event.event_type == "FAILURE":
        db.execute(
            """
            UPDATE vocabulary_items
            SET mistake_count_total = mistake_count_total + 1,
                status = 'LEARNING',
                mastery_level = CASE WHEN mastery_level > 2 THEN 2 ELSE mastery_level END,
                last_mistake_at = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (occurred_at, occurred_at, occurred_at, item_id),
        )
    else:
        # Unknown/meaning/spelling requests are explicitly NOT mistakes.
        db.execute(
            "UPDATE vocabulary_items SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (occurred_at, occurred_at, item_id),
        )

    # Conservative mastery evidence.
    if event.event_type == "RECOGNITION":
        db.execute(
            "UPDATE vocabulary_items SET mastery_level = MAX(mastery_level, 2) WHERE id = ?",
            (item_id,),
        )
    elif event.event_type == "PROMPTED_SUCCESS":
        db.execute(
            "UPDATE vocabulary_items SET mastery_level = MAX(mastery_level, 3), last_success_at = ? WHERE id = ?",
            (occurred_at, item_id),
        )
    elif event.event_type == "NATURAL_SUCCESS":
        db.execute(
            "UPDATE vocabulary_items SET mastery_level = MAX(mastery_level, 3), last_success_at = ? WHERE id = ?",
            (occurred_at, item_id),
        )
    elif event.event_type == "SPONTANEOUS_SUCCESS":
        db.execute(
            """
            UPDATE vocabulary_items
            SET spontaneous_success_count = spontaneous_success_count + 1,
                mastery_level = MAX(mastery_level, 3),
                last_success_at = ?
            WHERE id = ?
            """,
            (occurred_at, item_id),
        )

    # Keep compact operational evidence on the item so archived raw events are
    # never needed during a normal session.
    item = db.execute("SELECT * FROM vocabulary_items WHERE id = ?", (item_id,)).fetchone()
    qualifying_week_values = _json_list(item["qualifying_spontaneous_weeks_json"])
    qualifies = (
        event.event_type == "SPONTANEOUS_SUCCESS"
        and not event.agent_prompted_target
        and not event.agent_supplied_immediately_before
        and not event.learning_question
        and event.hint_level == 0
    )
    if qualifies and week not in qualifying_week_values:
        qualifying_week_values.append(week)
        qualifying_week_values.sort()
        db.execute(
            """
            UPDATE vocabulary_items
            SET qualifying_spontaneous_weeks_json = ?
            WHERE id = ?
            """,
            (json.dumps(qualifying_week_values), item_id),
        )
    qualifying_weeks = len(qualifying_week_values)

    if qualifying_weeks >= 2:
        # A failure event in this same operation wins over historical success:
        # learned vocabulary can return to LEARNING.
        if event.event_type != "FAILURE":
            db.execute(
                """
                UPDATE vocabulary_items
                SET status = 'LEARNED',
                    mastery_level = MAX(mastery_level, 4),
                    learned_at = COALESCE(learned_at, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (occurred_at, occurred_at, item_id),
            )

    item = db.execute("SELECT * FROM vocabulary_items WHERE id = ?", (item_id,)).fetchone()

    return VocabularyEventResult(
        success=True,
        key=item["key"],
        status=item["status"],
        mastery_level=item["mastery_level"],
        difficulty=item["difficulty"],
        mistake_count_total=item["mistake_count_total"],
        spontaneous_success_count=item["spontaneous_success_count"],
        qualifying_spontaneous_weeks=qualifying_weeks,
        learned_at=item["learned_at"],
    )


GRAMMAR_MISTAKE_EVENTS = {
    "LEARNING_ERROR",
    "RECURRING_ERROR",
    "REACTIVATION_FAILURE",
}

GRAMMAR_SUCCESS_EVENTS = {
    "CORRECT_USAGE",
    "NATURAL_SUCCESS",
    "SPONTANEOUS_SUCCESS",
    "REACTIVATION_SUCCESS",
}


def normalize_grammar_key(key: str) -> str:
    value = unicodedata.normalize("NFC", key).strip().casefold()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^0-9a-zà-ÿ_+\-]", "", value)
    return value


def _updated_grammar_outcomes(
    existing: list[str],
    event_type: str,
    limit: int = 12,
) -> list[str]:
    outcomes = existing[-limit:]
    if event_type in GRAMMAR_MISTAKE_EVENTS:
        outcomes.append("M")
    elif event_type in GRAMMAR_SUCCESS_EVENTS:
        outcomes.append("S")
    return outcomes[-limit:]


def _grammar_status(recent_correct: int, recent_mistakes: int, latest_event_type: str) -> str:
    # Fresh regression wins over the moving average.
    if latest_event_type in GRAMMAR_MISTAKE_EVENTS:
        return "ACTIVE"

    recent_total = recent_correct + recent_mistakes
    recent_error_rate = (recent_mistakes / recent_total) if recent_total else 0.0

    if recent_correct >= 5 and recent_mistakes == 0:
        return "STABLE"

    if recent_correct >= 3 and recent_error_rate <= 0.25:
        return "IMPROVING"

    return "ACTIVE"


def record_grammar_event(
    db: sqlite3.Connection,
    event: GrammarEventRequest,
) -> GrammarEventResult:
    session = db.execute(
        "SELECT id FROM sessions WHERE id = ?",
        (event.session_id,),
    ).fetchone()
    if session is None:
        raise ValueError("Unknown session_id")

    normalized = normalize_grammar_key(event.key)
    if not normalized:
        raise ValueError("Grammar key cannot be empty")

    dt = _parse_event_time(event.occurred_at)
    occurred_at = dt.isoformat()
    week = _calendar_week(dt)

    item = db.execute(
        "SELECT * FROM grammar_items WHERE language = ? AND key = ?",
        (event.language, normalized),
    ).fetchone()

    if item is None:
        usefulness = event.usefulness_score if event.usefulness_score is not None else 3
        db.execute(
            """
            INSERT INTO grammar_items (
                language, key, display_name, description, usefulness_score,
                correct_usage_count, mistake_count_total, status, error_rate,
                priority_score, first_seen_at, last_seen_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 0, 0, 'ACTIVE', 0.0, 0.0, ?, ?, ?, ?)
            """,
            (
                event.language, normalized, event.display_name, event.description,
                usefulness, occurred_at, occurred_at, occurred_at, occurred_at,
            ),
        )
        item_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        item_id = item["id"]

    if event.display_name is not None:
        db.execute("UPDATE grammar_items SET display_name = ? WHERE id = ?", (event.display_name, item_id))
    if event.description is not None:
        db.execute("UPDATE grammar_items SET description = ? WHERE id = ?", (event.description, item_id))
    if event.usefulness_score is not None:
        db.execute("UPDATE grammar_items SET usefulness_score = ? WHERE id = ?", (event.usefulness_score, item_id))

    db.execute(
        """
        INSERT INTO grammar_events (
            session_id, grammar_item_id, created_at, event_type,
            session_subject, event_subject, user_form, correct_form,
            explanation, review_method, hint_level, retrieval_speed,
            agent_prompted_target, calendar_week, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.session_id, item_id, occurred_at, event.event_type,
            event.session_subject, event.event_subject, event.user_form,
            event.correct_form, event.explanation, event.review_method,
            event.hint_level, event.retrieval_speed,
            int(event.agent_prompted_target), week, event.notes,
        ),
    )
    db.execute(
        """
        UPDATE sessions
        SET grammar_event_count = grammar_event_count + 1
        WHERE id = ?
        """,
        (event.session_id,),
    )

    if event.event_type in GRAMMAR_MISTAKE_EVENTS:
        db.execute(
            """
            UPDATE grammar_items
            SET mistake_count_total = mistake_count_total + 1,
                last_mistake_at = ?, last_seen_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (occurred_at, occurred_at, occurred_at, item_id),
        )
    elif event.event_type in GRAMMAR_SUCCESS_EVENTS:
        db.execute(
            """
            UPDATE grammar_items
            SET correct_usage_count = correct_usage_count + 1,
                last_success_at = ?, last_seen_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (occurred_at, occurred_at, occurred_at, item_id),
        )

    item = db.execute("SELECT * FROM grammar_items WHERE id = ?", (item_id,)).fetchone()

    total_correct = item["correct_usage_count"]
    total_mistakes = item["mistake_count_total"]
    total = total_correct + total_mistakes
    historical_error_rate = (total_mistakes / total) if total else 0.0

    recent_outcomes = _updated_grammar_outcomes(
        _json_list(item["recent_outcomes_json"]),
        event.event_type,
    )
    recent_correct = recent_outcomes.count("S")
    recent_mistakes = recent_outcomes.count("M")
    recent_total = recent_correct + recent_mistakes
    recent_error_rate = (recent_mistakes / recent_total) if recent_total else 0.0

    usefulness = item["usefulness_score"]
    priority_score = usefulness * recent_error_rate
    status = _grammar_status(recent_correct, recent_mistakes, event.event_type)

    db.execute(
        """
        UPDATE grammar_items
        SET error_rate = ?, priority_score = ?, status = ?,
            recent_outcomes_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            historical_error_rate,
            priority_score,
            status,
            json.dumps(recent_outcomes),
            occurred_at,
            item_id,
        ),
    )

    item = db.execute("SELECT * FROM grammar_items WHERE id = ?", (item_id,)).fetchone()

    return GrammarEventResult(
        success=True,
        key=item["key"],
        status=item["status"],
        usefulness_score=item["usefulness_score"],
        correct_usage_count=item["correct_usage_count"],
        mistake_count_total=item["mistake_count_total"],
        recent_correct_count=recent_correct,
        recent_mistake_count=recent_mistakes,
        error_rate=item["error_rate"],
        recent_error_rate=recent_error_rate,
        priority_score=item["priority_score"],
        last_mistake_at=item["last_mistake_at"],
        last_success_at=item["last_success_at"],
    )
