# LinguaWalk API — V3

This is the initial backend for the LinguaWalk custom GPT.

## Included

- SQLite database initialization
- FastAPI app
- Bearer API-key authentication
- `GET /health`
- `GET /profile`
- `GET /progress`
- `GET /learning/targets`
- `POST /session/start`
- `POST /session/end`
- Learner profile loading
- Initial vocabulary/grammar target loading

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create an API key:

```bash
export LINGUAWALK_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "$LINGUAWALK_API_KEY"
```

Initialize the DB:

```bash
python db.py
```

Run the API:

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Start a session:

```bash
curl -X POST http://127.0.0.1:8000/session/start   -H "Authorization: Bearer $LINGUAWALK_API_KEY"   -H "Content-Type: application/json"   -d '{
    "primary_language": "FRENCH",
    "secondary_language": "ENGLISH",
    "session_type": "MORNING_WALK",
    "session_subject": "Daily news recap"
  }'
```

Interactive docs:

```text
http://127.0.0.1:8000/docs
```

Generated OpenAPI:

```text
http://127.0.0.1:8000/openapi.json
```

Do not expose the service publicly while using the default API key.

## Container

Build and test the production image locally:

```bash
docker build -t linguawalk:local .
docker run --rm -p 127.0.0.1:8000:8000 \
  -e LINGUAWALK_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  -v linguawalk-data:/app/data \
  linguawalk:local
```

The image runs as UID/GID `10001`, uses one Uvicorn worker, and stores SQLite at `/app/data/linguawalk.db`.

The k3s manifests and deployment instructions are in `../k8s/`.

## Consolidation and archive boundary

`consolidation.py` creates weekly or monthly global and per-item summaries for completed periods. The operation is atomic: summary writes and `archived_at` markers commit together, or all changes roll back. Retrying an already archived period returns its stored result without rewriting snapshots or scanning raw events.

Raw vocabulary and grammar rows remain append-only evidence. Normal learning decisions use compact state stored on item rows, while session closure uses counters stored on the session. Existing V3 databases are upgraded additively; the new operational fields are backfilled once when their columns are introduced.

Consolidation remains an internal server function. `/session/start` automatically catches up completed periods containing unarchived evidence and ensures the immediately previous week/month is summarized even when it had no activity. Current-period evidence remains active. Rollover and session creation share one immediate SQLite transaction, and the existing `maintenance` response flags report whether weekly or monthly work ran. There is no GPT-facing maintenance endpoint.

## Hidden learning targets

The `targets` returned by `/session/start` are due D+2/D+7/D+14/D+30-style reactivations or current-week failures. Vocabulary ranking uses mastery, difficulty, status and mistake history; grammar ranking uses usefulness and current weakness. Learned vocabulary and stable grammar can return when retention is due.

Each target includes `next_review_at`, a concise selection reason and a state-based `recommended_method`. The method is an exercise choice for the next review, not a claim that immediate success proved the method effective. Target selection reads current item state only and does not scan archived raw events.

## Profile and progress

`GET /profile` returns the stored baseline, CEFR dimensions, strengths, weaknesses, learning-method preferences and current vocabulary/grammar counts. `GET /progress` returns lifetime session/event totals from session-owned counters, current item-state totals and the latest consolidated week/month. `GET /learning/targets` exposes the same due-target calculation used by session start.

All three routes require the Bearer API key. Their normal reads use profile, session, item and summary tables only; archived event tables remain outside the normal API read path.

## Session end

`POST /session/end` closes a session with normalized subjects, a summary and
learner notes. The first successful close owns the server timestamp and stored
summary. Retrying the same operation is safe: the response sets
`already_ended` to `true` and returns the original closure. The response also
reports vocabulary, grammar and total event counts for the session.


## V2 vocabulary endpoint

`POST /vocabulary/event` now implements the vocabulary learning state machine.

Important rules:

- Meaning/spelling/unknown-word events create or update the word but do not count as mistakes.
- `FAILURE` increments the mistake counter.
- Two qualifying `SPONTANEOUS_SUCCESS` events in two distinct ISO calendar weeks mark a word `LEARNED`.
- Prompted usage, direct answers to learning questions, strongly hinted usage and usage immediately after the agent supplied the word do not qualify.
- A later `FAILURE` moves a learned word back to `LEARNING`.

Run the complete automated suite with:

```bash
python -m unittest discover -p 'test_*.py' -v
```


## V3 grammar engine

`POST /grammar/event` implements grammar tracking.

Current rules:

- No automatic `LEARNED` state for grammar.
- Statuses: `ACTIVE`, `IMPROVING`, `STABLE`.
- Priority uses current weakness:
  `priority_score = usefulness_score × recent_error_rate`.
- Historical `error_rate` remains stored separately.
- Five recent correct uses with no recent mistake can produce `STABLE`.
- A fresh genuine mistake immediately returns the item to `ACTIVE`.
- Lower-usefulness grammar is retained but receives less daily priority.
