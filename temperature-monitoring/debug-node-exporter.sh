#!/usr/bin/env bash

set -euo pipefail

# Supply live names through the environment so diagnostics remain reusable.
NAMESPACE="${NAMESPACE:-monitoring}"
STUCK_POD="${STUCK_POD:?set STUCK_POD to the pod to inspect}"
TARGET_NODE="${TARGET_NODE:?set TARGET_NODE to the node to inspect}"

echo "=== 1. Checking Pod Status and Event Log ==="
kubectl describe pod "$STUCK_POD" -n "$NAMESPACE"

echo -e "\n=== 2. Inspecting Recent Namespace Events ==="
kubectl get events -n "$NAMESPACE" --sort-by='.metadata.creationTimestamp' | tail -n 20

echo -e "\n=== 3. Checking Node Status for $TARGET_NODE ==="
kubectl describe node "$TARGET_NODE" | grep -A 10 "Conditions:"

echo -e "\n=== 4. Checking K3s Kubelet logs on $TARGET_NODE via Proxmox Host L2 ==="
echo "Run this command manually inside '$TARGET_NODE' to inspect runtime blocks:"
echo "-> sudo journalctl -u k3s-agent | tail -n 50"
