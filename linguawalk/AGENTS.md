# LinguaWalk — Codex Agent Instructions

You are continuing development of **LinguaWalk**, a personal adaptive language-learning backend used by a Custom GPT during ~1-hour walking conversations.

Read before changing code:
1. `PROJECT_STATUS.md`
2. `ARCHITECTURE.md`
3. `LEARNING_RULES.md`
4. `DEPLOYMENT.md`
5. `NEXT_TASKS.md`

Inspect the existing source and tests before modifying behavior.

## Primary objective

Continue LinguaWalk incrementally while preserving the agreed learning semantics. The immediate goal is to deploy the current API to the user's existing k3s homelab. Then continue session lifecycle, consolidation, target selection, profile/progress endpoints, and finally safe public HTTPS exposure for a Custom GPT Action.

## Engineering rules

- Do not silently redesign agreed learning rules.
- Prefer small, testable changes.
- Backend owns IDs, timestamps, counters, status transitions, priorities, consolidation and archival.
- GPT/API clients report observations/events; they do not directly mutate calculated state.
- Event tables are append-only evidence in normal operation.
- Current item tables are calculated operational state.
- Keep raw `sqlite3` unless there is a strong documented reason to change.
- Keep one FastAPI replica and one Uvicorn worker while SQLite is used.
- Never commit secrets.
- Add tests for state-machine changes.
- Run all existing tests before declaring work complete.
- Archived daily/raw events must not be analyzed during normal sessions after consolidation. They are available only when the user explicitly requests archive/history analysis.

## Technology

Python, FastAPI, SQLite/sqlite3, Uvicorn, k3s, Traefik, Longhorn, Bearer API-key authentication.

## Security

Learning history is private. Public exposure must require HTTPS and authentication. Never expose SQLite or unrestricted admin/history endpoints.
