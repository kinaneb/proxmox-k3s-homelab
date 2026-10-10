# LinguaWalk k3s manifests

These manifests keep the SQLite deployment at one pod and use `Recreate` so an
upgrade cannot briefly run two writers against the same database. Longhorn
provides the persistent `/app/data` volume; the API key remains outside Git.

Before deployment:

1. Copy `../k8s-overlays/local.example` to the ignored
   `../k8s-overlays/local` directory and set the private registry image,
   immutable tag, and internal DNS name.
2. Configure that local DNS name to resolve to the Traefik LoadBalancer.
3. Create the Secret without storing its value in Git:

   ```bash
   kubectl apply -f namespace.yaml
   kubectl -n linguawalk create secret generic linguawalk-api \
     --from-literal=api-key="$(openssl rand -hex 32)"
   ```

4. Review the rendered resources, then apply them:

   ```bash
   kubectl kustomize ../k8s-overlays/local
   kubectl apply -k ../k8s-overlays/local
   ```

`secret.example.yaml` documents the required object shape and is deliberately
excluded from `kustomization.yaml` so its placeholder cannot be deployed by the
normal apply command.

The Traefik Ingress applies two namespaced middlewares. One limits each source
to 60 requests per minute with a burst of 30; the other adds response headers
that disable framing, MIME sniffing, referrer forwarding and unused browser
features. HSTS is deliberately absent while this route remains HTTP-only.
