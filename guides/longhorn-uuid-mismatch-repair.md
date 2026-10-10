# Guide: Longhorn Disk UUID Mismatch Repair (`DiskFilesystemChanged`)

This guide outlines the diagnostic steps and resolution procedure when a Longhorn storage node reports `DiskFilesystemChanged` / `record diskUUID doesn't match the one on the disk`.

---

## 💡 Technical Background

1. **Longhorn Disk Identification**:
   * Longhorn tracks node storage paths (e.g. `/var/lib/longhorn`) using a hidden metadata configuration file located at `/var/lib/longhorn/longhorn-disk.cfg`.
   * This JSON file contains a generated `diskName` and `diskUUID`.
2. **Cause of `DiskFilesystemChanged`**:
   * If a node VM is recreated, re-formatted, or if `/var/lib/longhorn` is re-initialized, a new `longhorn-disk.cfg` is generated with a fresh UUID.
   * Longhorn's Kubernetes Custom Resource (`node.longhorn.io/<node-name>`) retains the original `diskUUID` in `status.diskStatus`.
   * Longhorn intentionally flags `Ready: False` to protect replica data from un-intended overwrites.

---

## 🛠️ Step-by-Step Troubleshooting Procedure

### Step 1: Check Longhorn Node Custom Resource Status

Check the recorded `diskUUID` and `diskName` in the node CRD status:

```bash
kubectl get node.longhorn.io -n longhorn-system <NODE_NAME> -o yaml
```

Look for `status.diskStatus.<disk-id>`:
```yaml
diskStatus:
  default-disk-new:
    conditions:
    - message: 'Disk default-disk-new(/var/lib/longhorn) on node worker-2 is not ready: record diskUUID doesn''t match the one on the disk'
      reason: DiskFilesystemChanged
      status: "False"
      type: Ready
    diskName: default-disk-ff57408671ae651f
    diskUUID: replace-with-disk-uuid
```

---

### Step 2: Verify Host Filesystem & Replica Integrity

Deploy a temporary diagnostic pod to read the current `/var/lib/longhorn/longhorn-disk.cfg` and verify that `/var/lib/longhorn/replicas/` exists:

```bash
kubectl run read-lh-cfg --image=busybox --restart=Never --overrides='{
  "spec": {
    "nodeName": "<NODE_NAME>",
    "containers": [{
      "name": "c",
      "image": "busybox",
      "command": ["cat", "/host/var/lib/longhorn/longhorn-disk.cfg"],
      "volumeMounts": [{"name": "h", "mountPath": "/host"}]
    }],
    "volumes": [{"name": "h", "hostPath": {"path": "/"}}]
  }
}' && sleep 3 && kubectl logs read-lh-cfg && kubectl delete pod read-lh-cfg
```

---

### Step 3: Align `longhorn-disk.cfg` with Recorded CRD Metadata

To restore the disk to `Ready` status without re-syncing or losing existing volume replicas, update `/var/lib/longhorn/longhorn-disk.cfg` to match the exact `diskName` and `diskUUID` from the CRD:

```bash
kubectl run fix-lh-cfg --image=busybox --restart=Never --overrides='{
  "spec": {
    "nodeName": "<NODE_NAME>",
    "containers": [{
      "name": "c",
      "image": "busybox",
      "command": ["sh", "-c", "echo '\''{\"diskName\":\"<RECORDED_DISK_NAME>\",\"diskUUID\":\"<RECORDED_DISK_UUID>\",\"diskDriver\":\"\"}'\'' > /host/var/lib/longhorn/longhorn-disk.cfg"],
      "volumeMounts": [{"name": "h", "mountPath": "/host"}]
    }],
    "volumes": [{"name": "h", "hostPath": {"path": "/"}}]
  }
}' && sleep 3 && kubectl delete pod fix-lh-cfg
```

---

### Step 4: Restart `longhorn-manager` Pod to Force Re-scan

Find and delete the `longhorn-manager` pod running on the affected node to trigger an immediate disk re-probe:

```bash
# Find manager pod on target node
kubectl get pods -n longhorn-system -l app=longhorn-manager --field-selector spec.nodeName=<NODE_NAME>

# Delete the pod to restart it
kubectl delete pod -n longhorn-system <LONGHORN_MANAGER_POD_NAME>
```

---

### Step 5: Verify Disk & Volume Health

Verify that the node disk status returns to `Ready: True`:

```bash
# Check node disk readiness
kubectl get node.longhorn.io -n longhorn-system <NODE_NAME> -o yaml

# Verify all Longhorn volumes are healthy
kubectl get volume.longhorn.io -n longhorn-system
```
