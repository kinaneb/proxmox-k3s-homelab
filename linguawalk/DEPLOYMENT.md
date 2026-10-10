# LinguaWalk — k3s Deployment

## Existing cluster

```text
control-1  control-plane,etcd  198.51.100.11
control-2  control-plane,etcd  198.51.100.12
control-3  control-plane,etcd  198.51.100.13
worker-1  worker              198.51.100.21
worker-2  worker              198.51.100.22
worker-3  worker              198.51.100.23
```

All are k3s `v1.34.5+k3s1`, Debian 13, containerd 2.1.5-k3s1.

Storage:

```text
local-path (default) rancher.io/local-path
longhorn   (default) driver.longhorn.io
longhorn-static      driver.longhorn.io
```

Two classes appear marked default. Do not rely on defaults. LinguaWalk must explicitly use:

```yaml
storageClassName: longhorn
```

IngressClass:

```text
traefik -> traefik.io/ingress-controller
```

Traefik service is LoadBalancer and currently exposes 80/443 on the cluster node LAN addresses.

## Desired shape

```text
namespace linguawalk
Traefik Ingress
  -> ClusterIP Service :8000
  -> FastAPI Deployment, replicas=1
  -> /app/data
  -> Longhorn PVC, initially 1Gi
```

SQLite architecture requires one replica and one Uvicorn worker.

## Container baseline

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV LINGUAWALK_DB_PATH=/app/data/linguawalk.db
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

Improve non-root execution/layer hygiene if cleanly possible.

## Secret

Never commit a real key. Example manual creation:

```bash
kubectl create namespace linguawalk
kubectl -n linguawalk create secret generic linguawalk-api   --from-literal=api-key="$(openssl rand -hex 32)"
```

Deployment consumes it via `secretKeyRef`.

## Registry

The live registry endpoint was reconfirmed on 2026-09-20:

```text
198.51.100.11:30500
```

`registry-service` exposes registry port 5000 through NodePort 30500, the registry Deployment is healthy and uses `registry-pvc`, and the build machine marks this endpoint as insecure/trusted. Existing k3s workloads reference the same endpoint. Build the LinguaWalk image for `linux/amd64` because the cluster nodes are x86_64, then verify a fresh pull on k3s.

Inspect:

```bash
kubectl get ingress -A
kubectl get svc -A | grep -Ei 'registry|gitea'
docker info | grep -A5 -i "Insecure Registries"
```

The remaining registry acceptance check is a push followed by a fresh k3s pull of the immutable LinguaWalk image tag.

## Internal acceptance criteria

Before public exposure:
1. image builds;
2. k3s can pull it;
3. namespace exists;
4. Secret exists;
5. Longhorn PVC Bound;
6. pod Running/Ready;
7. `/health` through Service;
8. `/health` through internal Traefik;
9. authenticated `/session/start`;
10. database survives pod deletion/rescheduling;
11. vocabulary/grammar state survives restart.

All 11 criteria passed on 2026-09-20 using image `198.51.100.11:30500/linguawalk:6286070`. The persistence test wrote explicit acceptance markers, replaced the pod, verified both markers through `/session/start`, and then removed only those test records. The learner tables were clean after validation. The live Ingress uses `linguawalk.example.invalid`; LAN DNS must resolve that name to the Traefik LoadBalancer addresses.

Phase 5 image `198.51.100.11:30500/linguawalk:165af95` was rolled out on 2026-09-20. Authenticated session start, first close and idempotent retry passed through Traefik; the validation session was removed afterward.

## Public exposure

Custom GPT Actions ultimately require a publicly reachable HTTPS endpoint. Do not use RFC1918 or `.local`.

First validate internal deployment. Then choose controlled DNS/TLS/exposure. Require HTTPS + Bearer auth and expose only the minimal API. Do not broadly expose the homelab or database.

The live path is Tailscale Funnel through `linguawalk-public.example.invalid`. The gateway uses a loopback-only Nginx bridge on port `18080` to the private Traefik host, so Funnel publishes only LinguaWalk and requires no inbound router forwarding. Nginx allowlists `/health` plus the seven Action routes and returns `404` for framework and unrecognized paths. Public validation passed with trusted TLS, `200` health, `401` without the Bearer key, `200` with the existing key, and `404` for `/openapi.json`. The gateway playbook is idempotent and `linguawalk_funnel_enabled: false` is the rollback switch.
