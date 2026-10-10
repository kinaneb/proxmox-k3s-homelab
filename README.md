# Proxmox & K3s Homelab — Linux Infrastructure Automation

> Public-safe documentation uses RFC 5737 example addresses and neutral host
> names. Live site identity is stored only in ignored `*.local.*` files; start
> from [config/site.local.env.example](config/site.local.env.example).

For a new clone, create the local files before deployment:

```bash
cp config/site.local.env.example config/site.local.env
cp cluster-management/inventory/hosts.local.ini.example \
  cluster-management/inventory/hosts.local.ini
```

Replace every example value locally. Ansible host variables, application
manifests, generated reports, and Kubernetes overlays follow the same
`*.example` → ignored `*.local.*` convention.

Google credentials, including service-account JSON files, are private keys.
Keep the real file outside Git and copy only the required values into protected
Forgejo Actions secrets. [config/google-service-account.example.json](config/google-service-account.example.json)
documents the expected shape without containing a usable credential.

This repository documents a hands-on **Linux infrastructure and DevOps homelab**: virtualization with **Proxmox VE**, a multi-node **Kubernetes (K3s)** cluster, **Ansible** configuration management, and operational tooling for deployment, observability, and recovery. It is organized as a monorepo of playbooks, Kubernetes manifests, scripts, and runbooks.

## Why I Built This

This homelab is my reproducible environment for experimenting with Linux infrastructure, Kubernetes workloads, and distributed systems without depending on my workstation.

It runs a six-node K3s cluster across three Proxmox hosts and is partially automated with Ansible. The environment includes distributed persistent storage with Longhorn, ingress with Traefik, and observability with Prometheus, Grafana, and Alertmanager.

This repository contains the public-safe automation, deployment manifests, operational procedures, monitoring configuration, and failure-recovery work developed while operating the lab. It intentionally represents **partial infrastructure reproducibility**, not full bare-metal disaster recovery: initial Proxmox setup, parts of VM provisioning/bootstrap, and persistent application-data recovery have separate requirements.

## Engineering Work Demonstrated

The repository focuses on practical infrastructure engineering rather than a turnkey production platform:

- **Linux systems administration and automation:** Debian host maintenance, SSH access, configuration management, and repeatable operational tasks using Ansible and Bash.
- **Virtualization and container orchestration:** Proxmox VE virtual machines, a multi-node Kubernetes/K3s environment, workload manifests, and cluster lifecycle operations.
- **Persistent storage and networking:** Longhorn replicated volumes, Traefik ingress, and network configuration for services hosted across nodes.
- **Monitoring and reliability:** Prometheus metrics, Grafana dashboards, Alertmanager notifications, infrastructure health checks, and documented recovery procedures.
- **Infrastructure security practices:** local-only configuration templates, secret scanning, and separation of public examples from private environment settings.

These examples reflect hands-on homelab operation. Some setup and recovery steps are manual, and configurations should be reviewed before use in another environment.

---

## 📂 Subprojects & Directories

### 🛠️ [Cluster Management (cluster-management/)](cluster-management)
*   **Purpose**: Ansible playbooks and inventory configurations for hypervisor tuning, K3s cluster deployments, host orchestration, lifecycle upgrades, and automated reconciliation.
*   **Quick Links**:
    *   [Host Inventory Example](cluster-management/inventory/hosts.local.ini.example)
    *   [Debian 13.7 VM Rolling Upgrade](cluster-management/playbooks/upgrade-trixie-vms.yaml)
    *   [Longhorn Storage Guard Playbook](cluster-management/playbooks/longhorn-storage-guard.yml)
    *   [Proxmox Host Tuning Playbook](cluster-management/playbooks/pve-host-tuning.yaml)
    *   [K3s Worker Node Reconciler](cluster-management/playbooks/k3s-node-tuning.yaml)
*   **Documentation**: See the [Cluster Management README](cluster-management/README.md) for usage and run instructions.

### 📊 [Temperature Monitoring (temperature-monitoring/)](temperature-monitoring)
*   **Purpose**: Prometheus metrics scraping, Alertmanager alert definitions, Grafana dashboards, and Discord notification routings for hardware thermal states.
*   **Quick Links**:
    *   [Thermal Alert Rules](temperature-monitoring/thermal-alerts-all.yaml)
    *   [Alertmanager Discord Config](temperature-monitoring/alertmanager-config.yaml)
    *   [Proxmox Exporter Endpoint](temperature-monitoring/proxmox-monitor.yaml)
*   **Documentation**: See the [Temperature Monitoring README](temperature-monitoring/README.md) for configurations and routing details.

### 🔮 [System State Mapping (cluster_status_export/)](cluster_status_export)
*   **Purpose**: Live, compiled state maps of physical hypervisors, active cluster pods/nodes, and Unraid array storage pools, populated by the discovery loop.
*   *   [01-infrastructure.md](cluster_status_export/01-infrastructure.example.md) (Proxmox nodes LVM & virtualization state)
*   *   [02-cluster.md](cluster_status_export/02-cluster.example.md) (Live K3s pods and service routes)
*   *   [03-storage.md](cluster_status_export/03-storage.example.md) (Unraid hardware, network, sensors, disk/pool health, and SMB shares)

---

## 🌐 Central Infrastructure Overview

*   **Virtualization**: Three Proxmox VE hosts running Linux virtual machines.
*   **Storage Services**: An Unraid host providing network file shares and storage monitoring. See [storage integration](cluster-management/README.md#unraid-storage-server) and the [sanitized storage report](cluster_status_export/03-storage.example.md).
*   **Kubernetes**: Six-node K3s cluster (three control-plane nodes and three workers) on Debian Linux.
*   **Additional Workloads**: Standalone virtual machines managed alongside the cluster.
*   **Persistent Volumes**: Longhorn with filesystem UUID-based mount protection and systemd startup dependencies.
*   **Ingress**: Traefik for HTTP routing.
*   **Source Control**: Self-hosted Forgejo for internal development; this GitHub repository is the public portfolio copy.

---

## 🤖 Mentoring & Management Rules
All updates, commits, and actions performed within this repository adhere strictly to the directives outlined in the [AGENTS.md](AGENTS.md) guide and the master state dashboard in [PROJECT_STATE.md](PROJECT_STATE.md).
