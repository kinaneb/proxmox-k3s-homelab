#!/bin/bash

set -euo pipefail

KASM_HOST="${KASM_HOST:?set KASM_HOST from config/site.local.env}"

# STREAMING_CHUNK: Locating Kasm pods across the cluster...

echo "=== 1. CHECKING KASM POD STATUS ==="

# This will find the Kasm pods regardless of which namespace you deployed them in.

# We want to ensure they are in a 'Running' state and 1/1 (or similar) ready.

kubectl get pods -A | grep -i kasm

# STREAMING_CHUNK: Checking Kasm service port mappings...

echo -e "\n=== 2. CHECKING KASM SERVICE & PORTS ==="

# This verifies if the Kasm service exists, what namespace it is in,

# and what internal/external ports it is listening on (e.g., 443, 3000, or 8443).

kubectl get svc -A | grep -i kasm

# STREAMING_CHUNK: Inspecting Traefik Ingress rules for the configured host...

echo -e "\n=== 3. CHECKING TRAEFIK INGRESS ROUTES ==="

# Since you use Traefik, Kasm is likely exposed via an Ingress or IngressRoute.

# This command finds the routing rule tying the configured host to the service.

kubectl get ingress,ingressroute -A | grep -i kasm

# STREAMING_CHUNK: Testing local DNS resolution...

echo -e "\n=== 4. TESTING DNS & LOCAL CONNECTION ==="

# Finally, ask Traefik for the configured host.

# The -k flag ignores self-signed certificate warnings, and -v gives us the routing headers.

curl -kv "https://${KASM_HOST}"
