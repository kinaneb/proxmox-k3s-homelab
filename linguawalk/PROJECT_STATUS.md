# LinguaWalk — Project Status

## Product

LinguaWalk is an adaptive French/English conversation coach for daily ~1-hour morning walks. French is the main conversation language; English is used strategically for short explanations, grammar comparisons, meanings and spelling.

Desired conversational behavior:
- roughly 75% French conversation, 15% English explanation, 10% review/testing;
- learner speaks about 60–70%;
- start with roughly 2–3 current/reliable news stories;
- news is a conversation starter, not a long briefing;
- hidden review should feel like natural conversation.

## Current backend: V3

Current structure:

```text
linguawalk/
├── app/                     # FastAPI source, schema, tests and container
├── k8s/                     # Kustomize-ready k3s manifests
├── ARCHITECTURE.md
├── DEPLOYMENT.md
├── LEARNING_RULES.md
└── NEXT_TASKS.md
```

Implemented endpoints:
- `GET /health`
- `GET /profile`
- `GET /progress`
- `GET /learning/targets`
- `POST /session/start`
- `POST /session/end`
- `POST /vocabulary/event`
- `POST /grammar/event`

Bearer auth protects learning endpoints; `/health` is unauthenticated.

### Vocabulary engine

Implemented/tested:
- unknown/meaning/spelling requests create/update an item without counting a mistake;
- `FAILURE` increments mistake count;
- two qualifying spontaneous correct uses in two different ISO weeks => `LEARNED`, mastery >= 4;
- prompted use/direct learning-question answers do not qualify;
- later genuine failure returns `LEARNED` to `LEARNING`;
- historical evidence remains.

Statuses: `NOT_LEARNED`, `LEARNING`, `LEARNED`.

Mastery:
1 UNKNOWN
2 RECOGNITION
3 ASSISTED PRODUCTION
4 INDEPENDENT PRODUCTION
5 STABLE MASTERY

### Grammar engine

Statuses: `ACTIVE`, `IMPROVING`, `STABLE`. There is intentionally no automatic grammar `LEARNED` state.

Implemented/tested:
- mistake events increment lifetime mistakes;
- meaningful tracked successes increment correct usage;
- historical error rate retained;
- recent error rate models current weakness;
- `priority_score ≈ usefulness_score × recent_error_rate`;
- fresh genuine mistake immediately returns concept to `ACTIVE`;
- current heuristic: `IMPROVING` after enough recent success/low error;
- current heuristic: `STABLE` after 5 recent correct uses with no recent mistake.

Correct usage counts are meaningful observed/tracked uses, not every grammatically correct sentence.

### Tests

Validated on 2026-09-22: 6 vocabulary + 6 grammar + 3 session lifecycle + 6 consolidation + 3 automatic-rollover + 4 hidden-target + 4 read-API + 3 Action-schema = 35 passing tests in one discovery run. The suite covers state transitions, session-close retries, completed-period validation, transactional rollback, immutable consolidation retries, archive-safe operational reads, in-place V3 schema migration, missed-period catch-up, ISO year boundaries, scheduled target ranking, profile/progress responses and the public Action contract.

## Deployment progress

- Phase 0 complete: V3 baseline reproduced and verified.
- Phase 1 complete: non-root image, one Uvicorn worker, database at `/app/data/linguawalk.db`; native development image built and runtime-tested.
- Phase 2 complete: namespace, explicit 1 GiB Longhorn PVC, one-replica `Recreate` Deployment, Secret-based API key, ClusterIP Service, Traefik Ingress, probes, security context and resources. YAML lint, Kustomize render and kubectl client dry-run pass.
- Phase 3 complete: immutable `linux/amd64` image `198.51.100.11:30500/linguawalk:6286070` was pushed and freshly pulled by k3s on `control-2` (registry digest `sha256:2a0e805bb939b802c2cfeac3fa1f69dac6a5e0b7288082109cd51ff1e79432e6`).
- Phase 4 complete: namespace, random API Secret, 1 GiB Longhorn PVC, Deployment, Service and Traefik Ingress are live. Health passed through the Service and Ingress, unauthenticated access returned `401`, authenticated session/event writes succeeded, and vocabulary plus grammar state survived a controlled pod replacement. Acceptance records were removed afterward, leaving the learner tables clean.
- The Ingress uses permanent internal host `linguawalk.example.invalid`; a matching LAN DNS record is still required for name-based client access.
- Phase 5 complete: `POST /session/end` stores normalized subjects, summary, learner notes and a server-owned end timestamp; returns per-type and total event counts; and preserves the first closure on safe retries. Image `198.51.100.11:30500/linguawalk:165af95` is live with registry digest `sha256:75f252f301d5e4c27e3df76c4ee9bca9917533a6898529729cce43e7e583a5f5`; first-close and retry behavior passed through Traefik. The validation session was removed afterward.
- Phase 6 complete: completed weeks and months produce transactional per-item plus global summaries, mark raw events archived, and return the stored result unchanged on retry. Compact operational evidence on item/session rows keeps normal session work independent of archived event scans. Existing V3 databases receive additive columns and a one-time evidence backfill. Image `198.51.100.11:30500/linguawalk:26e7842` is live with registry digest `sha256:0ce770369776f05a8c58a10343a8deb80f1371929b8d6810065a905adc74ad09`; rollout, startup, schema migration, SQLite integrity, PVC and Traefik health checks passed.
- Phase 7 complete: `/session/start` consolidates completed periods with unarchived evidence plus the immediately prior week/month, leaves the current period active, and reports whether weekly or monthly maintenance ran. Rollover and session creation share one immediate SQLite transaction, so concurrent starts serialize and partial maintenance cannot survive a failed start. Image `198.51.100.11:30500/linguawalk:46cbb7a` is live with registry digest `sha256:f8e989aedde727b257879b89954c98f7ed7ebd983685be34ae463a9d7d86de02`; the first live start returned both flags `true`, the retry returned both `false`, and the two validation sessions were removed with SQLite integrity `ok`.
- Phase 8 complete: session-start targets use D+2/D+7/D+14/D+30-style schedules derived from current item state, include current-week failures, reactivate learned/stable items when due, and rank vocabulary by mastery/difficulty/history and grammar by usefulness/current weakness. Targets include the next review timestamp and a state-based recommended method. Selection does not scan raw event tables. Image `198.51.100.11:30500/linguawalk:b19287c` is live with registry digest `sha256:72316adf959767ce1d27297fad307be1ddeb5f29aefb1b79c894161108d588eb`; production-container target selection passed, and live Traefik health/OpenAPI plus SQLite integrity checks passed without creating validation records.
- Phase 9 complete: authenticated profile, progress and explicit target endpoints expose baseline/preferences, current counts, lifetime session/event totals, latest consolidated summaries and scheduled targets. Profile/progress reads use profile, session, item and summary tables only; they do not scan raw event evidence. Image `198.51.100.11:30500/linguawalk:23e609e` is live with registry digest `sha256:00e31dc4e409fafed5ff36789343fdde131ce40eb9557e5242da3414a5065a20`; all three routes returned `200` with the existing Bearer key and `401` without it through Traefik, while health and SQLite integrity remained clean.
- Phase 10 complete: Tailscale Funnel on the existing gateway publishes `linguawalk-public.example.invalid` on HTTPS 443 without direct WAN forwarding. The gateway has one declarative network manager, persistent LAN/default routes and an idempotent loopback-only Nginx bridge. Nginx allowlists `/health` plus the seven Action paths. Public TLS, security headers, `200` health, `401` without authentication, `200` with the existing Bearer key, `404` for `/openapi.json` and a zero-change Ansible rerun passed.
- Phase 11 schema generation complete: `gpt-action.openapi.json` derives from FastAPI, uses the verified public URL, is 47,198 bytes and includes exactly the seven learning operations with stable IDs and Bearer security. The exporter rejects HTTP/private server URLs, and all 35 tests pass. GPT-editor import and Preview testing remain.
- Phase 12 preparation complete: paste-ready Custom GPT instructions define French-first conversation, verified-current-news openings, one-session Action lifecycle, hidden retrieval practice, precise vocabulary/grammar event classification, concise correction and spelling flows, baseline limitations, safe retry behavior and archive boundaries. A 14-scenario Preview evaluation set covers the main conversational and persistence failure modes. Live evaluation remains dependent on the public Action endpoint.

## Database

Current tables:
1. sessions
2. vocabulary_items
3. vocabulary_events
4. grammar_items
5. grammar_events
6. learner_profile
7. weekly_summaries
8. monthly_summaries
9. weekly_vocabulary_summaries
10. weekly_grammar_summaries
11. monthly_vocabulary_summaries
12. monthly_grammar_summaries

`vocabulary_events` and `grammar_events` remain append-only evidence. Consolidation sets `archived_at` for completed periods without deleting records or changing lifetime totals. Normal learning and session-close paths use compact state stored on `vocabulary_items`, `grammar_items`, and `sessions`; raw history is read by consolidation or explicit archive work only.

## Remaining work

- LAN DNS record for `linguawalk.example.invalid`;
- import the final Custom GPT Action schema and API key in the GPT editor;
- run the 14-scenario Preview evaluation against the live endpoint.

The seven-operation public Action intentionally has no profile-write or raw-archive route. Baseline creation therefore remains a backend/admin workflow, and the GPT can store only tentative observations in session notes when no baseline exists. Detailed archive retrieval remains unavailable unless a later, explicitly scoped history endpoint is added.
