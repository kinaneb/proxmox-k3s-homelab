# Homelab Monorepo Dashboard (homeLab)

Public examples in this document use documentation-only addresses and neutral
host names. The ignored local inventory and generated `.local.md` reports are
the source of truth for the deployed environment.

This document serves as the master tracking status for your entire homelab infrastructure, configuration playbooks, and service monitoring rules.

---

## 1. Subproject Directory Structure

### 📂 [cluster-management/](cluster-management)
*   **Purpose**: Ansible playbooks, roles, group variables, host-specific variables, and inventory mappings.
*   **Target Hosts**: Proxmox nodes (`hypervisor-1`-`hypervisor-3`), K3s master/worker VMs, standalone VMs (`gateway-1`), and the Unraid Storage Host.
*   **Key Blueprints**:
    *   [hosts.local.ini.example](cluster-management/inventory/hosts.local.ini.example)
    *   [upgrade-trixie-vms.yaml](cluster-management/playbooks/upgrade-trixie-vms.yaml)
    *   [longhorn-storage-guard.yml](cluster-management/playbooks/longhorn-storage-guard.yml)
    *   [pve-host-tuning.yaml](cluster-management/playbooks/pve-host-tuning.yaml)
    *   [k3s-node-tuning.yaml](cluster-management/playbooks/k3s-node-tuning.yaml)

### 📂 [temperature-monitoring/](temperature-monitoring)
*   **Purpose**: Prometheus, Alertmanager, and Grafana YAML manifests for tracking homelab temps.
*   **Key Blueprints**:
    *   [thermal-alerts-all.yaml](temperature-monitoring/thermal-alerts-all.yaml) (CPU and SSD threshold triggers)
    *   [alertmanager-config.yaml](temperature-monitoring/alertmanager-config.yaml) (Discord webhook mapping)
    *   [proxmox-monitor.yaml](temperature-monitoring/proxmox-monitor.yaml) / [unraid-monitor.yaml](temperature-monitoring/unraid-monitor.yaml) (Scrape targets)

### 📂 [cluster_status_export/](cluster_status_export)
*   **Purpose**: Ground-truth mappings generated automatically by the discovery script.
*   *   [01-infrastructure.md](cluster_status_export/01-infrastructure.example.md) (Proxmox nodes compute/LVM status)
*   *   [02-cluster.md](cluster_status_export/02-cluster.example.md) (K3s master/worker node and pod matrices)
*   *   [03-storage.md](cluster_status_export/03-storage.example.md) (Unraid physical disks, array, and SMB share status)

---

## 2. Infrastructure Blueprint Ground Truth

### Proxmox Hypervisors
*   `hypervisor-1`: `192.0.2.21`
*   `hypervisor-2`: `192.0.2.22`
*   `hypervisor-3`: `192.0.2.23`

### Unraid Data Server
*   **Platform**: Unraid storage server (`storage-1` public alias).
*   **Services**: NFS/SMB sharing, ZFS storage, node exporter, and temperature monitoring.
*   **Network**: Site-specific addresses, paths, and gateway settings remain private.

### K3s HA Cluster Nodes (Debian Linux)
*   **Masters**: `control-1` (`198.51.100.11`), `control-2` (`198.51.100.12`), `control-3` (`198.51.100.13`)
*   **Workers**: `worker-1` (`198.51.100.21`), `worker-2` (`198.51.100.22`), `worker-3` (`198.51.100.23`)

### Standalone VMs
*   `gateway-1`: `192.0.2.40` (VMID 9400 on `hypervisor-1`)

---

## 3. Latest Sessions & Enhancements

### Session: Debian 13.7 Upgrade & Storage Guard (2026-09-19)
1.  **Debian 13.7 Point Release Rolling Upgrade**:
    *   Deployed `cluster-management/playbooks/upgrade-trixie-vms.yaml` for rolling zero-downtime upgrades.
    *   Implemented graceful cordon and drain on Kubernetes nodes, with explicit service stops before reboot to prevent unclean storage unmounts.
    *   Pinned `node-ip: "{{ ansible_host }}"` on K3s masters to prevent IPv6 SLAAC address mismatch during reboot.
    *   Updated the Linux kernel on K3s control-plane and worker VMs.
2.  **Longhorn Worker Storage Identity & Startup Guard**:
    *   Recorded permanent filesystem UUIDs and Longhorn disk UUIDs in `cluster-management/inventory/host_vars/worker-[1-3].yml`.
    *   Deployed `cluster-management/playbooks/longhorn-storage-guard.yml` to purge legacy `/dev/sd*` fstab entries and replace them with immutable UUID-based entries.
    *   Configured systemd drop-ins (`RequiresMountsFor=/var/lib/longhorn`) so the `k3s-agent` service waits for storage mounts before initialization.
3.  **Proxmox & Inventory Cleanups**:
    *   Fixed Proxmox playbook execution (`become: false`) across `configure-unattended-upgrades.yaml` and `patch-cluster.yaml` since connections are natively root.
    *   Removed obsolete ProxyJump entries in `hosts.ini`, transitioning to direct host SSH keys.
    *   Integrated `standalone_vms` group (`gateway-1`).
4.  **Unraid State Reconciliation**:
    *   Verified SMB sharing and default routing configuration.

### Session: Storage Hardware Migration (2026-09-17)
* Updated inventory and architecture references for storage server.
* Extended discovery script to capture DMI identity, sensors, disk models, and ZFS cache pool.

### Session: Initial Monorepo Consolidation (2026-07-23)
* Monorepo re-organization for `cluster-management/`, `temperature-monitoring/`, `kasm/`, and `yaws-app/`.
* Persistent Longhorn volume claim for `docker-registry`.
* Traefik `IngressRoute` conversion for `kasm`.
* Proxmox LVM thinpool optimization with `discard=on` and `fstrim`.

---

## 4. Active Tasks & Backlog
- [x] Perform rolling upgrade of Debian 13 (Trixie) VMs to 13.7.
- [x] Protect Longhorn mount points against boot race conditions using systemd mount dependencies.
- [x] Add standalone VMs to inventory and upgrade workflows.
- [x] Verify Unraid MicroServer Gen10 storage state and SMB share configuration.
- [ ] Monitor Kasm database crashloop in `kasm` namespace (`kasm-db-1-19-0-0`).
