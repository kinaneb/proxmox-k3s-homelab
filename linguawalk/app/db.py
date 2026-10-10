import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH, SCHEMA_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = connect()
    try:
        conn.executescript(schema)
        added_columns = _migrate_existing_schema(conn)
        _backfill_operational_evidence(conn, added_columns)
        now = utc_now()
        conn.execute(
            "INSERT OR IGNORE INTO learner_profile (id, created_at, updated_at) VALUES (1, ?, ?)",
            (now, now),
        )
        conn.commit()
    finally:
        conn.close()


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> bool:
    if column not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        return True
    return False


def _migrate_existing_schema(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    added_columns = set()

    if _ensure_column(
        conn,
        "sessions",
        "vocabulary_event_count",
        "INTEGER NOT NULL DEFAULT 0",
    ):
        added_columns.add(("sessions", "vocabulary_event_count"))
    if _ensure_column(
        conn,
        "sessions",
        "grammar_event_count",
        "INTEGER NOT NULL DEFAULT 0",
    ):
        added_columns.add(("sessions", "grammar_event_count"))
    if _ensure_column(
        conn,
        "vocabulary_items",
        "qualifying_spontaneous_weeks_json",
        "TEXT NOT NULL DEFAULT '[]'",
    ):
        added_columns.add(("vocabulary_items", "qualifying_spontaneous_weeks_json"))
    if _ensure_column(
        conn,
        "grammar_items",
        "recent_outcomes_json",
        "TEXT NOT NULL DEFAULT '[]'",
    ):
        added_columns.add(("grammar_items", "recent_outcomes_json"))
    if _ensure_column(conn, "vocabulary_events", "archived_at", "TEXT"):
        added_columns.add(("vocabulary_events", "archived_at"))
    if _ensure_column(
        conn,
        "vocabulary_events",
        "agent_supplied_immediately_before",
        "INTEGER NOT NULL DEFAULT 0 CHECK (agent_supplied_immediately_before IN (0,1))",
    ):
        added_columns.add(("vocabulary_events", "agent_supplied_immediately_before"))
    if _ensure_column(conn, "grammar_events", "archived_at", "TEXT"):
        added_columns.add(("grammar_events", "archived_at"))
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_vocab_events_archive ON vocabulary_events(archived_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grammar_events_archive ON grammar_events(archived_at)"
    )
    return added_columns


def _backfill_operational_evidence(
    conn: sqlite3.Connection,
    added_columns: set[tuple[str, str]],
) -> None:
    session_assignments = []
    if ("sessions", "vocabulary_event_count") in added_columns:
        session_assignments.append(
            """vocabulary_event_count = (
                SELECT COUNT(*) FROM vocabulary_events
                WHERE vocabulary_events.session_id = sessions.id
            )"""
        )
    if ("sessions", "grammar_event_count") in added_columns:
        session_assignments.append(
            """grammar_event_count = (
                SELECT COUNT(*) FROM grammar_events
                WHERE grammar_events.session_id = sessions.id
            )"""
        )
    if session_assignments:
        conn.execute(f"UPDATE sessions SET {', '.join(session_assignments)}")

    if ("vocabulary_items", "qualifying_spontaneous_weeks_json") in added_columns:
        vocabulary_items = conn.execute(
            "SELECT id FROM vocabulary_items"
        ).fetchall()
        for item in vocabulary_items:
            weeks = [
                row["calendar_week"]
                for row in conn.execute(
                    """
                    SELECT DISTINCT calendar_week
                    FROM vocabulary_events
                    WHERE vocabulary_item_id = ?
                      AND event_type = 'SPONTANEOUS_SUCCESS'
                      AND agent_prompted_target = 0
                      AND agent_supplied_immediately_before = 0
                      AND learning_question = 0
                      AND hint_level = 0
                      AND calendar_week IS NOT NULL
                    ORDER BY calendar_week
                    """,
                    (item["id"],),
                )
            ]
            if weeks:
                conn.execute(
                    """
                    UPDATE vocabulary_items
                    SET qualifying_spontaneous_weeks_json = ?
                    WHERE id = ?
                    """,
                    (json.dumps(weeks), item["id"]),
                )

    if ("grammar_items", "recent_outcomes_json") in added_columns:
        grammar_items = conn.execute("SELECT id FROM grammar_items").fetchall()
        for item in grammar_items:
            rows = conn.execute(
                """
                SELECT event_type
                FROM grammar_events
                WHERE grammar_item_id = ?
                  AND event_type IN (
                    'LEARNING_ERROR', 'RECURRING_ERROR', 'REACTIVATION_FAILURE',
                    'CORRECT_USAGE', 'NATURAL_SUCCESS', 'SPONTANEOUS_SUCCESS',
                    'REACTIVATION_SUCCESS'
                  )
                ORDER BY id DESC
                LIMIT 12
                """,
                (item["id"],),
            ).fetchall()
            outcomes = [
                "M" if row["event_type"] in {
                    "LEARNING_ERROR", "RECURRING_ERROR", "REACTIVATION_FAILURE"
                } else "S"
                for row in reversed(rows)
            ]
            if outcomes:
                conn.execute(
                    "UPDATE grammar_items SET recent_outcomes_json = ? WHERE id = ?",
                    (json.dumps(outcomes), item["id"]),
                )


if __name__ == "__main__":
    init_db()
    print(f"Initialized database: {DB_PATH}")
