import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from db import utc_now


VOCABULARY_SUCCESS_EVENTS = {
    "RECOGNITION",
    "PROMPTED_SUCCESS",
    "NATURAL_SUCCESS",
    "SPONTANEOUS_SUCCESS",
}
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


@dataclass(frozen=True)
class ConsolidationResult:
    period_type: str
    period_key: str
    vocabulary_item_count: int
    grammar_item_count: int
    vocabulary_event_count: int
    grammar_event_count: int
    newly_archived_event_count: int
    consolidated_at: str


@dataclass(frozen=True)
class RolloverResult:
    weekly_consolidation_performed: bool
    monthly_consolidation_performed: bool


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _week_bounds(week: str) -> tuple[date, date]:
    match = re.fullmatch(r"(\d{4})-W(\d{2})", week)
    if match is None:
        raise ValueError("Week must use ISO format YYYY-Www")
    try:
        start = date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
    except ValueError as exc:
        raise ValueError("Invalid ISO week") from exc
    return start, start + timedelta(days=7)


def _month_bounds(month: str) -> tuple[date, date]:
    match = re.fullmatch(r"(\d{4})-(\d{2})", month)
    if match is None:
        raise ValueError("Month must use format YYYY-MM")
    try:
        start = date(int(match.group(1)), int(match.group(2)), 1)
    except ValueError as exc:
        raise ValueError("Invalid calendar month") from exc
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def _week_key(value: date) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _require_completed_period(end_exclusive: date, today: date) -> None:
    if end_exclusive > today:
        raise ValueError("Only completed periods can be consolidated")


def _event_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_count(
    db: sqlite3.Connection,
    start: date,
    end_exclusive: date,
) -> int:
    return sum(
        1
        for row in db.execute("SELECT started_at FROM sessions")
        if start <= _event_time(row["started_at"]).date() < end_exclusive
    )


def _most_used_review_method(events: list[sqlite3.Row]) -> str | None:
    counts = Counter(
        event["review_method"]
        for event in events
        if event["review_method"]
    )
    if not counts:
        return None
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]


def _group_events(
    events: list[sqlite3.Row],
    item_column: str,
) -> dict[int, list[sqlite3.Row]]:
    grouped: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for event in events:
        grouped[event[item_column]].append(event)
    return grouped


def _upsert_vocabulary_summary(
    db: sqlite3.Connection,
    table: str,
    period_column: str,
    period_key: str,
    item: sqlite3.Row,
    events: list[sqlite3.Row],
    consolidated_at: str,
) -> None:
    event_types = Counter(event["event_type"] for event in events)
    qualifying_count = sum(
        1
        for event in events
        if event["event_type"] == "SPONTANEOUS_SUCCESS"
        and not event["agent_prompted_target"]
        and not event["agent_supplied_immediately_before"]
        and not event["learning_question"]
        and event["hint_level"] == 0
    )
    db.execute(
        f"""
        INSERT INTO {table} (
            {period_column}, vocabulary_item_id, language, key,
            attempt_count, mistake_count, recognition_count,
            prompted_success_count, natural_success_count,
            spontaneous_success_count, qualifying_spontaneous_success_count,
            lifetime_mistake_count, status, mastery_level, difficulty,
            last_seen_at, last_mistake_at, last_success_at,
            most_used_review_method, consolidated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT({period_column}, vocabulary_item_id) DO UPDATE SET
            language = excluded.language,
            key = excluded.key,
            attempt_count = excluded.attempt_count,
            mistake_count = excluded.mistake_count,
            recognition_count = excluded.recognition_count,
            prompted_success_count = excluded.prompted_success_count,
            natural_success_count = excluded.natural_success_count,
            spontaneous_success_count = excluded.spontaneous_success_count,
            qualifying_spontaneous_success_count = excluded.qualifying_spontaneous_success_count,
            lifetime_mistake_count = excluded.lifetime_mistake_count,
            status = excluded.status,
            mastery_level = excluded.mastery_level,
            difficulty = excluded.difficulty,
            last_seen_at = excluded.last_seen_at,
            last_mistake_at = excluded.last_mistake_at,
            last_success_at = excluded.last_success_at,
            most_used_review_method = excluded.most_used_review_method,
            consolidated_at = excluded.consolidated_at
        """,
        (
            period_key,
            item["id"],
            item["language"],
            item["key"],
            len(events),
            event_types["FAILURE"],
            event_types["RECOGNITION"],
            event_types["PROMPTED_SUCCESS"],
            event_types["NATURAL_SUCCESS"],
            event_types["SPONTANEOUS_SUCCESS"],
            qualifying_count,
            item["mistake_count_total"],
            item["status"],
            item["mastery_level"],
            item["difficulty"],
            max(event["created_at"] for event in events),
            max(
                (event["created_at"] for event in events if event["event_type"] == "FAILURE"),
                default=None,
            ),
            max(
                (
                    event["created_at"]
                    for event in events
                    if event["event_type"] in VOCABULARY_SUCCESS_EVENTS
                ),
                default=None,
            ),
            _most_used_review_method(events),
            consolidated_at,
        ),
    )


def _upsert_grammar_summary(
    db: sqlite3.Connection,
    table: str,
    period_column: str,
    period_key: str,
    item: sqlite3.Row,
    events: list[sqlite3.Row],
    consolidated_at: str,
) -> None:
    mistake_count = sum(
        1 for event in events if event["event_type"] in GRAMMAR_MISTAKE_EVENTS
    )
    success_count = sum(
        1 for event in events if event["event_type"] in GRAMMAR_SUCCESS_EVENTS
    )
    db.execute(
        f"""
        INSERT INTO {table} (
            {period_column}, grammar_item_id, language, key,
            attempt_count, mistake_count, success_count,
            lifetime_mistake_count, lifetime_correct_count,
            usefulness_score, error_rate, priority_score, status,
            last_seen_at, last_mistake_at, last_success_at,
            most_used_review_method, consolidated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT({period_column}, grammar_item_id) DO UPDATE SET
            language = excluded.language,
            key = excluded.key,
            attempt_count = excluded.attempt_count,
            mistake_count = excluded.mistake_count,
            success_count = excluded.success_count,
            lifetime_mistake_count = excluded.lifetime_mistake_count,
            lifetime_correct_count = excluded.lifetime_correct_count,
            usefulness_score = excluded.usefulness_score,
            error_rate = excluded.error_rate,
            priority_score = excluded.priority_score,
            status = excluded.status,
            last_seen_at = excluded.last_seen_at,
            last_mistake_at = excluded.last_mistake_at,
            last_success_at = excluded.last_success_at,
            most_used_review_method = excluded.most_used_review_method,
            consolidated_at = excluded.consolidated_at
        """,
        (
            period_key,
            item["id"],
            item["language"],
            item["key"],
            len(events),
            mistake_count,
            success_count,
            item["mistake_count_total"],
            item["correct_usage_count"],
            item["usefulness_score"],
            item["error_rate"],
            item["priority_score"],
            item["status"],
            max(event["created_at"] for event in events),
            max(
                (
                    event["created_at"]
                    for event in events
                    if event["event_type"] in GRAMMAR_MISTAKE_EVENTS
                ),
                default=None,
            ),
            max(
                (
                    event["created_at"]
                    for event in events
                    if event["event_type"] in GRAMMAR_SUCCESS_EVENTS
                ),
                default=None,
            ),
            _most_used_review_method(events),
            consolidated_at,
        ),
    )


def _current_state_counts(db: sqlite3.Connection) -> sqlite3.Row:
    return db.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM vocabulary_items WHERE status = 'LEARNING') AS vocabulary_learning,
          (SELECT COUNT(*) FROM vocabulary_items WHERE status = 'LEARNED') AS vocabulary_learned,
          (SELECT COUNT(*) FROM grammar_items WHERE status = 'ACTIVE') AS active_grammar,
          (SELECT COUNT(*) FROM grammar_items WHERE status = 'IMPROVING') AS improving_grammar,
          (SELECT COUNT(*) FROM grammar_items WHERE status = 'STABLE') AS stable_grammar
        """
    ).fetchone()


def _upsert_global_summary(
    db: sqlite3.Connection,
    period_type: str,
    period_key: str,
    start: date,
    end_exclusive: date,
    vocabulary_events: list[sqlite3.Row],
    grammar_events: list[sqlite3.Row],
    vocabulary_item_count: int,
    grammar_item_count: int,
    consolidated_at: str,
) -> None:
    state = _current_state_counts(db)
    vocabulary_mistakes = sum(
        1 for event in vocabulary_events if event["event_type"] == "FAILURE"
    )
    grammar_mistakes = sum(
        1 for event in grammar_events if event["event_type"] in GRAMMAR_MISTAKE_EVENTS
    )
    session_count = _session_count(db, start, end_exclusive)
    summary_json = json.dumps(
        {
            "archived": True,
            "vocabulary_item_count": vocabulary_item_count,
            "grammar_item_count": grammar_item_count,
            "vocabulary_event_count": len(vocabulary_events),
            "grammar_event_count": len(grammar_events),
        },
        sort_keys=True,
    )

    if period_type == "WEEK":
        db.execute(
            """
            INSERT INTO weekly_summaries (
                week, start_date, end_date, vocabulary_learning,
                vocabulary_learned, active_grammar, improving_grammar,
                stable_grammar, vocabulary_mistakes, grammar_mistakes,
                session_count, summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(week) DO UPDATE SET
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                vocabulary_learning = excluded.vocabulary_learning,
                vocabulary_learned = excluded.vocabulary_learned,
                active_grammar = excluded.active_grammar,
                improving_grammar = excluded.improving_grammar,
                stable_grammar = excluded.stable_grammar,
                vocabulary_mistakes = excluded.vocabulary_mistakes,
                grammar_mistakes = excluded.grammar_mistakes,
                session_count = excluded.session_count,
                summary_json = excluded.summary_json
            """,
            (
                period_key,
                start.isoformat(),
                (end_exclusive - timedelta(days=1)).isoformat(),
                state["vocabulary_learning"],
                state["vocabulary_learned"],
                state["active_grammar"],
                state["improving_grammar"],
                state["stable_grammar"],
                vocabulary_mistakes,
                grammar_mistakes,
                session_count,
                summary_json,
                consolidated_at,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO monthly_summaries (
                month, vocabulary_learning, vocabulary_learned,
                active_grammar, improving_grammar, stable_grammar,
                vocabulary_mistakes_month, grammar_mistakes_month,
                session_count, french_cefr, summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                vocabulary_learning = excluded.vocabulary_learning,
                vocabulary_learned = excluded.vocabulary_learned,
                active_grammar = excluded.active_grammar,
                improving_grammar = excluded.improving_grammar,
                stable_grammar = excluded.stable_grammar,
                vocabulary_mistakes_month = excluded.vocabulary_mistakes_month,
                grammar_mistakes_month = excluded.grammar_mistakes_month,
                session_count = excluded.session_count,
                french_cefr = excluded.french_cefr,
                summary_json = excluded.summary_json
            """,
            (
                period_key,
                state["vocabulary_learning"],
                state["vocabulary_learned"],
                state["active_grammar"],
                state["improving_grammar"],
                state["stable_grammar"],
                vocabulary_mistakes,
                grammar_mistakes,
                session_count,
                db.execute(
                    "SELECT overall_french_cefr FROM learner_profile WHERE id = 1"
                ).fetchone()[0],
                summary_json,
                consolidated_at,
            ),
        )


def _consolidate(
    db: sqlite3.Connection,
    period_type: str,
    period_key: str,
    start: date,
    end_exclusive: date,
    consolidated_at: str,
) -> ConsolidationResult:
    if period_type == "WEEK":
        vocabulary_events = db.execute(
            "SELECT * FROM vocabulary_events WHERE calendar_week = ? ORDER BY id",
            (period_key,),
        ).fetchall()
        grammar_events = db.execute(
            "SELECT * FROM grammar_events WHERE calendar_week = ? ORDER BY id",
            (period_key,),
        ).fetchall()
        vocabulary_table = "weekly_vocabulary_summaries"
        grammar_table = "weekly_grammar_summaries"
        period_column = "week"
        archive_filter = "calendar_week = ?"
    else:
        vocabulary_events = db.execute(
            "SELECT * FROM vocabulary_events WHERE substr(created_at, 1, 7) = ? ORDER BY id",
            (period_key,),
        ).fetchall()
        grammar_events = db.execute(
            "SELECT * FROM grammar_events WHERE substr(created_at, 1, 7) = ? ORDER BY id",
            (period_key,),
        ).fetchall()
        vocabulary_table = "monthly_vocabulary_summaries"
        grammar_table = "monthly_grammar_summaries"
        period_column = "month"
        archive_filter = "substr(created_at, 1, 7) = ?"

    vocabulary_groups = _group_events(vocabulary_events, "vocabulary_item_id")
    grammar_groups = _group_events(grammar_events, "grammar_item_id")

    for item_id, events in vocabulary_groups.items():
        item = db.execute(
            "SELECT * FROM vocabulary_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        _upsert_vocabulary_summary(
            db,
            vocabulary_table,
            period_column,
            period_key,
            item,
            events,
            consolidated_at,
        )

    for item_id, events in grammar_groups.items():
        item = db.execute(
            "SELECT * FROM grammar_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        _upsert_grammar_summary(
            db,
            grammar_table,
            period_column,
            period_key,
            item,
            events,
            consolidated_at,
        )

    _upsert_global_summary(
        db,
        period_type,
        period_key,
        start,
        end_exclusive,
        vocabulary_events,
        grammar_events,
        len(vocabulary_groups),
        len(grammar_groups),
        consolidated_at,
    )

    newly_archived = 0
    for table in ("vocabulary_events", "grammar_events"):
        cursor = db.execute(
            f"""
            UPDATE {table}
            SET archived_at = ?
            WHERE {archive_filter} AND archived_at IS NULL
            """,
            (consolidated_at, period_key),
        )
        newly_archived += cursor.rowcount

    return ConsolidationResult(
        period_type=period_type,
        period_key=period_key,
        vocabulary_item_count=len(vocabulary_groups),
        grammar_item_count=len(grammar_groups),
        vocabulary_event_count=len(vocabulary_events),
        grammar_event_count=len(grammar_events),
        newly_archived_event_count=newly_archived,
        consolidated_at=consolidated_at,
    )


def _run_consolidation(
    db: sqlite3.Connection,
    period_type: str,
    period_key: str,
    start: date,
    end_exclusive: date,
    today: date,
    consolidated_at: str,
) -> ConsolidationResult:
    _require_completed_period(end_exclusive, today)
    summary_table = "weekly_summaries" if period_type == "WEEK" else "monthly_summaries"
    period_column = "week" if period_type == "WEEK" else "month"
    existing = db.execute(
        f"SELECT summary_json, created_at FROM {summary_table} WHERE {period_column} = ?",
        (period_key,),
    ).fetchone()
    if existing is not None and existing["summary_json"]:
        summary = json.loads(existing["summary_json"])
        if summary.get("archived") is True:
            return ConsolidationResult(
                period_type=period_type,
                period_key=period_key,
                vocabulary_item_count=summary["vocabulary_item_count"],
                grammar_item_count=summary["grammar_item_count"],
                vocabulary_event_count=summary["vocabulary_event_count"],
                grammar_event_count=summary["grammar_event_count"],
                newly_archived_event_count=0,
                consolidated_at=existing["created_at"],
            )

    db.execute("SAVEPOINT linguawalk_consolidation")
    try:
        result = _consolidate(
            db,
            period_type,
            period_key,
            start,
            end_exclusive,
            consolidated_at,
        )
        db.execute("RELEASE SAVEPOINT linguawalk_consolidation")
        return result
    except Exception:
        db.execute("ROLLBACK TO SAVEPOINT linguawalk_consolidation")
        db.execute("RELEASE SAVEPOINT linguawalk_consolidation")
        raise


def consolidate_week(
    db: sqlite3.Connection,
    week: str,
    *,
    today: date | None = None,
    consolidated_at: str | None = None,
) -> ConsolidationResult:
    start, end_exclusive = _week_bounds(week)
    return _run_consolidation(
        db,
        "WEEK",
        week,
        start,
        end_exclusive,
        today or _utc_today(),
        consolidated_at or utc_now(),
    )


def consolidate_month(
    db: sqlite3.Connection,
    month: str,
    *,
    today: date | None = None,
    consolidated_at: str | None = None,
) -> ConsolidationResult:
    start, end_exclusive = _month_bounds(month)
    return _run_consolidation(
        db,
        "MONTH",
        month,
        start,
        end_exclusive,
        today or _utc_today(),
        consolidated_at or utc_now(),
    )


def _unarchived_period_keys(
    db: sqlite3.Connection,
    expression: str,
) -> set[str]:
    rows = db.execute(
        f"""
        SELECT {expression} AS period_key
        FROM vocabulary_events
        WHERE archived_at IS NULL
        UNION
        SELECT {expression} AS period_key
        FROM grammar_events
        WHERE archived_at IS NULL
        """
    ).fetchall()
    return {row["period_key"] for row in rows if row["period_key"]}


def _archived_summary_exists(
    db: sqlite3.Connection,
    table: str,
    period_column: str,
    period_key: str,
) -> bool:
    row = db.execute(
        f"SELECT summary_json FROM {table} WHERE {period_column} = ?",
        (period_key,),
    ).fetchone()
    if row is None or not row["summary_json"]:
        return False
    try:
        return json.loads(row["summary_json"]).get("archived") is True
    except (json.JSONDecodeError, AttributeError):
        return False


def consolidate_due_periods(
    db: sqlite3.Connection,
    *,
    today: date | None = None,
    consolidated_at: str | None = None,
) -> RolloverResult:
    rollover_date = today or _utc_today()
    timestamp = consolidated_at or utc_now()
    db.execute("SAVEPOINT linguawalk_rollover")
    try:
        weekly_keys = _unarchived_period_keys(db, "calendar_week")
        weekly_keys.add(_week_key(rollover_date - timedelta(days=7)))
        completed_weekly_keys = sorted(
            key
            for key in weekly_keys
            if _week_bounds(key)[1] <= rollover_date
        )

        monthly_keys = _unarchived_period_keys(db, "substr(created_at, 1, 7)")
        previous_month_date = rollover_date.replace(day=1) - timedelta(days=1)
        monthly_keys.add(_month_key(previous_month_date))
        completed_monthly_keys = sorted(
            key
            for key in monthly_keys
            if _month_bounds(key)[1] <= rollover_date
        )

        weekly_performed = False
        for week in completed_weekly_keys:
            if not _archived_summary_exists(db, "weekly_summaries", "week", week):
                consolidate_week(
                    db,
                    week,
                    today=rollover_date,
                    consolidated_at=timestamp,
                )
                weekly_performed = True

        monthly_performed = False
        for month in completed_monthly_keys:
            if not _archived_summary_exists(db, "monthly_summaries", "month", month):
                consolidate_month(
                    db,
                    month,
                    today=rollover_date,
                    consolidated_at=timestamp,
                )
                monthly_performed = True

        result = RolloverResult(
            weekly_consolidation_performed=weekly_performed,
            monthly_consolidation_performed=monthly_performed,
        )
        db.execute("RELEASE SAVEPOINT linguawalk_rollover")
        return result
    except Exception:
        db.execute("ROLLBACK TO SAVEPOINT linguawalk_rollover")
        db.execute("RELEASE SAVEPOINT linguawalk_rollover")
        raise
