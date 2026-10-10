# Codex Start Prompt

Run Codex from the root of the LinguaWalk repository and give it this prompt:

> Continue development of this LinguaWalk project.
>
> First read `AGENTS.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `LEARNING_RULES.md`, `DEPLOYMENT.md`, and `NEXT_TASKS.md` completely. Treat `LEARNING_RULES.md` as product requirements.
>
> Inspect the existing V3 code and tests before editing anything. Run the existing tests and verify the API locally.
>
> If V3 is healthy, implement Phase 1 and Phase 2 from `NEXT_TASKS.md`: containerize the API and create k3s manifests for the documented homelab. Use one replica, one Uvicorn worker, a 1Gi Longhorn PVC mounted at `/app/data`, Kubernetes Secret-based Bearer API key, Traefik ingress, and health probes.
>
> Do not invent a registry hostname, public hostname, API key, or TLS setup. Leave those parameterized and tell me exactly what information or commands you need next.
>
> Keep changes incremental, validate them, and update `PROJECT_STATUS.md` with what you actually completed.
