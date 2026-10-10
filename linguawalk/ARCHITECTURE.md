# LinguaWalk — Architecture

## Runtime

```text
Custom GPT
    |
 HTTPS + Bearer
    v
Public HTTPS endpoint (later)
    |
Traefik Ingress
    |
ClusterIP Service
    |
FastAPI Pod — 1 replica
    |
/app/data/linguawalk.db
    |
Longhorn PVC
```

## Ownership

GPT reports observations. Backend deterministically owns IDs, timestamps, ISO week/month, normalization, counters, vocabulary mastery/status, grammar status, error rates, priorities, learned timestamps, scheduling, consolidation and archive boundaries.

`vocabulary_events` / `grammar_events` = append-only evidence/history.
`vocabulary_items` / `grammar_items` = current calculated state plus compact evidence needed by state transitions.
`sessions` = lifecycle state plus event counters used when closing a session.

## Memory hierarchy

1. baseline
2. current/raw event log
3. weekly per-item summaries
4. monthly per-item summaries
5. learner profile
6. fixed config/rules

Do not create a physical table/file per date.

## Baseline

Create once after enough first-session evidence unless user explicitly requests a new baseline. Track CEFR separately from item mastery. Baseline should not be overwritten by routine updates.

## Event metadata

Preserve server timestamp, session ID, `session_subject`, `event_subject`, item type/key, user/correct form, meaning/explanation, review method, result, hint level, retrieval speed, context/notes and ISO week.

## Weekly/monthly summaries

The implemented normalized design is:

```text
weekly_summaries
weekly_vocabulary_summaries
weekly_grammar_summaries
monthly_summaries
monthly_vocabulary_summaries
monthly_grammar_summaries
```

Per-item summaries store attempts, period outcome counts, lifetime-count snapshots, difficulty or usefulness, mastery/status, last seen/mistake/success timestamps and the most-used review method. The method field is factual; method recommendations must wait for delayed-retention evidence.

Consolidation accepts only completed ISO weeks or calendar months. One SQLite savepoint covers per-item summaries, the global summary and archive markers. Unique period/item constraints prevent duplicates. Once a global summary records `"archived": true`, retries return that stored result without scanning events or rewriting the historical snapshot.

After consolidation, raw rows remain evidence and receive `archived_at`; lifetime totals remain on current item rows. Vocabulary qualifying weeks, the grammar 12-outcome window and per-session event counts are stored as compact operational state. The additive V3 migration backfills these fields once when it adds them. Ordinary startup and normal sessions do not scan archived event tables.

## Normal session read policy

Use current learner profile, latest monthly state, latest weekly state, current-week raw events, and baseline only when comparison is useful.

## Intended API

- POST `/session/start`
- GET `/learning/targets`
- POST `/vocabulary/event`
- POST `/grammar/event`
- POST `/session/end`
- GET `/profile`
- GET `/progress`

Maintenance should happen server-side, not through GPT maintenance actions.

`POST /session/start` is the rollover boundary. Using the same UTC timestamp as the new session, it consolidates completed periods that still contain unarchived evidence and ensures summaries exist for the immediately previous ISO week and calendar month. Current-week/current-month evidence remains active. An immediate SQLite transaction serializes concurrent starts and commits rollover plus the new session together. Response maintenance flags indicate whether weekly or monthly consolidation was performed.

## Hidden target scheduling

Session-start targets are calculated from current item rows after rollover. The latest mistake/success and current mastery/status determine D+2, D+7, D+14 or D+30 timing. Current-week failures remain eligible before their formal due timestamp. Learned vocabulary and stable grammar return as retention targets when due.

Vocabulary ranking combines schedule urgency, current-week failure, status, mastery, difficulty and lifetime mistakes. Grammar ranking combines schedule urgency, current-week failure, status, usefulness, current weakness and lifetime mistakes. `next_review_at` makes the schedule explicit. `recommended_method` is chosen from current state (`FRENCH_TO_ENGLISH`, `ENGLISH_TO_FRENCH`, `SENTENCE_CREATION`, `GRAMMAR_CORRECTION` or `COVERT_CONVERSATION`); it must not be interpreted as evidence of method effectiveness until delayed-retention outcomes support that conclusion.

## Read API boundary

`GET /profile`, `GET /progress` and `GET /learning/targets` use the same Bearer authentication as write routes. Profile reads the single learner-profile row plus current item counts. Progress combines session-owned counters, current vocabulary/grammar state and the latest weekly/monthly global summaries. Explicit targets reuse the session-start selector with the request-time UTC timestamp. None of these routes reads raw event evidence.
