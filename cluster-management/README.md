# Homelab Cluster Management (cluster-management)

Public examples use RFC 5737 addresses. Copy the inventory and variable
examples to their ignored `.local` paths before running Ansible.

```bash
cp inventory/hosts.local.ini.example inventory/hosts.local.ini
cp inventory/group_vars/all/site.local.yml.example \
  inventory/group_vars/all/site.local.yml
cp inventory/group_vars/k3s_workers/site.local.yml.example \
  inventory/group_vars/k3s_workers/site.local.yml
```

Create one ignored `inventory/host_vars/<inventory-host>.yml` file per machine
from the templates in `inventory/examples/host_vars/`. Keep disk UUIDs,
addresses, interface names, DNS servers, and login users in those local files.

### Forgejo runner identity and registration

The runner Deployment reads site values from `forgejo-runner-site` and the
registration credential from `forgejo-runner-registration`. Copy
`manifests/runner-site.example.yaml` to `runner-site.local.yaml`, fill in local
values, and apply it. Create the Secret directly from a newly rotated token:

```bash
kubectl -n forgejo-runners create secret generic \
  forgejo-runner-registration \
  --from-literal=token="$FORGEJO_RUNNER_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f manifests/runner-site.local.yaml
kubectl apply -f manifests/runner-deployment.yaml
unset FORGEJO_RUNNER_TOKEN
```

This directory contains the Infrastructure-as-Code (IaC) playbooks, variables, and inventories used to deploy, configure, and reconcile your Proxmox VE hypervisors and K3s high-availability Kubernetes cluster.

## Unraid storage server

Unraid provides network storage and hardware monitoring for the homelab.
The public inventory uses the neutral alias `storage-1`; live network
addresses, share paths, and hardware specifications remain in local-only configuration.

| Capability | Purpose |
|---|---|
| NFS and SMB | Shared file access |
| ZFS | Storage pool management |
| Node exporter | Host metrics |
| Hardware sensors | Temperature monitoring |

The [sanitized storage report](../cluster_status_export/03-storage.example.md)
shows the discovery output format without revealing live infrastructure details.

Discovery uses Ansible `raw` commands so Unraid does not need Python installed.
The existing Debian/Proxmox tuning and upgrade playbooks do not target Unraid.
See [temperature monitoring](../temperature-monitoring/README.md) for the AMD
sensor mapping.

---

## 📂 Subfolder Layout

*   **[inventory/](inventory)**: Contains target inventory lists (`hosts.ini`), group vars, and host vars mapping Proxmox nodes, K3s control planes, workers, and standalone VMs.
    *   `inventory/host_vars/worker-[1-3].yml`: Stores immutable filesystem and Longhorn disk UUIDs for reliable worker storage binding.
*   **[playbooks/](playbooks)**: Contains setup playbooks for server tuning, safety guards, and lifecycle upgrades:
    *   `upgrade-trixie-vms.yaml`: performs a controlled rolling upgrade of Debian 13 (Trixie) VMs to 13.7 with Kubernetes cordon/drain safety, etcd quorum preservation, and storage unmount safety.
    *   `longhorn-storage-guard.yml`: validates Longhorn worker storage identities (UUIDs), enforces fstab UUID-based mounts, and writes systemd drop-ins requiring storage before K3s agent startup.
    *   `k3s-worker-network.yml`: pins each worker to its recorded LAN address through ifupdown, performs a guarded serial handoff, restarts K3s so Flannel uses the canonical address, and verifies routes plus Kubernetes readiness.
    *   `tailscale-gateway-network.yml`: removes conflicting network ownership on `gateway-1`, persists `192.0.2.40/24` through ifupdown, and verifies Tailscale plus K3s ingress reachability.
    *   `linguawalk-funnel-gateway.yml`: reconciles a loopback-only Nginx bridge and the persistent Tailscale Funnel listener for the public LinguaWalk Action endpoint.
    *   `patch-cluster.yaml`: general rolling package patch and reboot management for K3s nodes and Proxmox hosts.
    *   `pve-host-tuning.yaml`: tunes physical Proxmox hypervisor storage, networks, and settings.
    *   `k3s-node-tuning.yaml`: reconciles worker node configurations, Longhorn mount ordering, and OS tuning.
*   **[scripts/](scripts)**: Operational helper scripts:
    *   `generate-sysmap.sh`: scans Proxmox hosts, Unraid, and K3s node states to compile active markdown systems status maps.

---

## 🚀 Execution & Usage

### 1. Prerequisites
Ensure Ansible is installed locally on your workstation, and your SSH key is authorized across all target servers.

### 2. Verify Inventory Connection
Run a ping module check against all hypervisor hosts:
```bash
ansible proxmox -i inventory/hosts.local.ini -m ping
```

### 3. Run Upgrade Playbook (Debian 13.7 Point Release)
To perform a rolling upgrade across all Trixie VMs:
```bash
ansible-playbook playbooks/upgrade-trixie-vms.yaml --ask-vault-pass
```

To upgrade only standalone VMs (e.g. `gateway-1`):
```bash
ansible-playbook playbooks/upgrade-trixie-vms.yaml --limit standalone_vms
```

To run only on K3s workers:
```bash
ansible-playbook playbooks/upgrade-trixie-vms.yaml --ask-vault-pass --tags workers
```

To run only on K3s control-plane masters:
```bash
ansible-playbook playbooks/upgrade-trixie-vms.yaml --ask-vault-pass --tags masters
```

### 4. Run Longhorn Storage Guard
To validate disk/filesystem UUIDs and guarantee mount-before-agent startup dependencies on workers:
```bash
ansible-playbook -i inventory/hosts.local.ini playbooks/longhorn-storage-guard.yml
```

### 5. Run Tuning Playbooks
To tune hypervisor host configuration parameters:
```bash
ansible-playbook -i inventory/hosts.local.ini playbooks/pve-host-tuning.yaml
```

To tune worker node configuration parameters:
```bash
ansible-playbook -i inventory/hosts.local.ini playbooks/k3s-node-tuning.yaml
```

### 6. Reconcile canonical K3s worker networks

To reconcile the canonical worker addresses one node at a time:

```bash
ansible-playbook -i inventory/hosts.local.ini playbooks/k3s-worker-network.yml \
  --ask-vault-pass
```

The playbook validates `worker-1`/`.218`, `worker-2`/`.228`, and
`worker-3`/`.238` before changing a network interface. It waits for each
worker to reconnect and return to Kubernetes `Ready` before continuing.

### 7. Reconcile the LinguaWalk Tailscale Funnel gateway

Reconcile the gateway network first, then apply its loopback-only proxy and
declared Funnel state:

```bash
ansible-playbook -i inventory/hosts.local.ini playbooks/tailscale-gateway-network.yml
ansible-playbook -i inventory/hosts.local.ini playbooks/linguawalk-funnel-gateway.yml
```

`linguawalk_funnel_enabled` in the gateway host variables is the public-exposure
switch. When true, the playbook persists HTTPS port 443 through Tailscale and
publishes only the eight allowlisted LinguaWalk paths through the loopback
proxy. Set it to false and rerun the playbook to remove that Funnel listener.

---

## 🔍 Discovery Mapping
You can run the system map generator locally at the monorepo root folder to compile and export live infrastructure states:
```bash
bash ./cluster-management/scripts/generate-sysmap.sh
```
This updates the status files under [cluster_status_export/](../cluster_status_export).

The generator can also run from this directory with `bash scripts/generate-sysmap.sh`.
It requires both `ansible` and `kubectl`, uses the current kubectl context, and
collects read-only infrastructure queries. Each report includes a UTC timestamp.
The Unraid report records DMI hardware identity, CPU and installed memory,
network interfaces and routes, available hardware sensors, disk models, SMB shares, and ZFS
pools.
