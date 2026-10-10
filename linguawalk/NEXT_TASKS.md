# LinguaWalk — Next Tasks

## Current execution status (2026-09-24)

- Phases 0–2 are complete and validated.
- Phases 3–9 are complete: the internal deployment passed health, authentication, Longhorn persistence, session lifecycle, additive schema migration, consolidation, automatic rollover, hidden target selection, profile/progress APIs and SQLite integrity checks. Current live image: `198.51.100.11:30500/linguawalk:23e609e`.
- Phase 9 profile/progress APIs are deployed; the full suite now has 35 tests including the validated Action exporter.
- Phase 10 is complete. Tailscale Funnel publishes `linguawalk-public.example.invalid` on HTTPS 443 through an idempotent loopback-only bridge. Public TLS, health, security headers, `401`/`200` Bearer behavior, path allowlisting and playbook idempotence passed. Add the LAN DNS record for `linguawalk.example.invalid` independently if name-based internal client access is desired.

## Phase 0 — Verify V3

Read handoff docs, inspect source/schema/tests, create venv, install requirements, initialize a temporary DB, run all tests, start API locally and verify existing endpoints.

Do not proceed past unexplained failing tests.

## Phase 1 — Containerize

Add `Dockerfile` and `.dockerignore`.

Requirements: one Uvicorn worker, `0.0.0.0:8000`, DB at `/app/data/linguawalk.db`, writable volume, no embedded secrets, preferably non-root, Kubernetes-friendly health behavior. Build/test locally.

## Phase 2 — Kubernetes manifests

Add approximately:

```text
k8s/
├── namespace.yaml
├── pvc.yaml
├── deployment.yaml
├── service.yaml
├── ingress.yaml
└── secret.example.yaml
```

Use namespace `linguawalk`, explicit Longhorn 1Gi PVC, one replica, `/app/data` mount, API key from Secret, ClusterIP :8000, Traefik ingress, `/health` readiness/liveness probes, small sensible resources.

Do not invent registry or public hostname; parameterize placeholders.

## Phase 3 — Registry

Inspect actual current registry using:

```bash
kubectl get ingress -A
kubectl get svc -A | grep -Ei 'registry|gitea'
docker info | grep -A5 -i "Insecure Registries"
```

Use the real registry. Build/tag/push and verify k3s pull.

## Phase 4 — Internal deployment

Verify namespace/resources/PVC/pod/logs. Test health through Service and Traefik, then authenticated endpoints. Delete pod and verify SQLite/state persistence.

## Phase 5 — Session end

Implement/test `POST /session/end` with session ID, subjects, summary and learner notes. Return useful event/session counts.

## Phase 6 — Per-item consolidation

Replace/extend aggregate-only summary design with normalized per-item weekly/monthly summaries. Make consolidation transactional and idempotent. Preserve lifetime totals. Completed raw periods become archive and are not used in normal analysis.

Implementation status: complete and deployed. Four normalized per-item tables supplement the global summaries. Consolidation accepts completed periods only, uses one transaction, preserves lifetime state, marks raw evidence with `archived_at`, and treats an archived summary as immutable on retry. Operational evidence stored on item/session rows removes archived-event scans from normal learning and session-close paths.

## Phase 7 — Automatic rollover

At `/session/start`, detect missing prior week/month consolidation, run it idempotently, then return maintenance flags.

Implementation status: complete and deployed. Session start catches up completed unarchived periods, records the immediately prior week/month even when quiet, and leaves the current period unconsolidated. One immediate SQLite transaction covers maintenance and session creation. The existing response flags report whether weekly or monthly work occurred; no GPT-facing maintenance endpoint was added.

## Phase 8 — Hidden target selector

Implement D+2/D+7/D+14/D+30-style reactivation plus current-week failures, grammar usefulness/current weakness, vocabulary mastery/difficulty/status and recommended method.

Implementation status: complete and deployed. The selector derives schedules from compact current item state, includes learned/stable items when due, returns `next_review_at` and state-based methods, and never reads archived event tables. Method recommendations describe the next exercise format; they do not claim measured effectiveness without delayed-retention evidence.

## Phase 9 — Profile/progress

Implement:
- `GET /profile`
- `GET /progress`
- `GET /learning/targets`

Avoid rescanning archived raw history unnecessarily.

Implementation status: complete and deployed. All three routes require Bearer authentication. Profile returns stored baseline, CEFR dimensions, strengths/weaknesses, method preferences and current counts. Progress returns session/event totals from session counters, current item-state totals and the latest immutable weekly/monthly summaries. No profile/progress query reads raw event tables.

## Phase 10 — Public HTTPS

Only after internal deployment works. Choose DNS/domain, TLS and controlled exposure. Keep Bearer auth and minimal routes.

Implementation status: complete and externally validated. Tailscale Funnel publishes `linguawalk-public.example.invalid` on HTTPS 443 and proxies to `127.0.0.1:18080`; router forwarding and separate DNS/TLS management are unnecessary. Nginx exposes only `/health` plus the seven Action paths. Public checks returned `200` for health, `401` without authentication, `200` with the existing Bearer key and `404` for `/openapi.json`; TLS verification and a zero-change Ansible rerun passed.

## Phase 11 — Custom GPT Action

Generate final OpenAPI using real public HTTPS base URL for:
- startSession
- getLearningTargets
- recordVocabularyEvent
- recordGrammarEvent
- endSession
- getLearnerProfile
- getLearningProgress

Implementation status: schema generation is complete. `gpt-action.openapi.json` uses the verified public HTTPS URL, is 47,198 bytes, and contains exactly these seven operations with Bearer security. The exporter validation and all 35 backend tests pass. Import and live GPT-editor Preview testing remain.

## Phase 12 — GPT instructions

Finalize French-first natural conversation, brief English corrections, current-news morning start, hidden review, retrieval-before-exposure, event reporting, baseline behavior, spelling flow and archive restrictions.

Implementation status: paste-ready instructions and a 14-scenario Preview evaluation set are implemented. They define the complete session lifecycle, exact event classification, current-news verification, hidden target use, correction and spelling flows, backend ownership, safe retry behavior, baseline limitations and the archive boundary. Final live evaluation depends on the Phase 10 public endpoint and GPT Action connection.

## Immediate Codex instruction

Import `gpt-action.openapi.json` into the GPT editor, configure the existing Kubernetes API key as Bearer authentication, paste `GPT_INSTRUCTIONS.md`, and run the 14-scenario Preview evaluation set.
