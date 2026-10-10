# Homelab Temperature Monitoring (temperature-monitoring)

This directory contains the Prometheus, Alertmanager, and Grafana configurations used to track physical server temperatures and alert on high-thermal conditions via Discord.

---

## 📂 Core Configurations

*   **[thermal-alerts-all.yaml](thermal-alerts-all.yaml)**: Defines the Prometheus rules (`PrometheusRule`) for thermal alerting.
    *   `CPUHighTemperature`: Triggers critical alerts when Intel `coretemp` or AMD `k10temp` CPU sensors exceed `85°C` for 5 minutes. The rule resolves the driver using `node_hwmon_chip_names`; `chip` itself is a hardware path.
    *   `SSDHighTemperature`: Triggers warning alerts if storage drives exceed `75°C` for 5 minutes (excluding the hot Samsung controller sensor `temp3` on `nvme_nvme0`).
*   **[alertmanager-config.yaml](alertmanager-config.yaml)**: Configures the notification routing engine (`AlertmanagerConfig`).
    *   Integrates with Discord webhook endpoints using secrets (`discord-webhook-secret`).
*   **[proxmox-monitor.yaml](proxmox-monitor.yaml)**: ServiceMonitor and static Endpoints for querying physical metrics from Proxmox VE hosts on port `9100`.
*   **[unraid-monitor.yaml](unraid-monitor.yaml)**: ServiceMonitor and Endpoints for the storage server running Unraid (`192.0.2.30:9100`). The node exporter runs natively on Unraid.
*   **[thermal-dashboard.yaml](thermal-dashboard.yaml)**: Grafana dashboard JSON resource for visualizing CPU core temperatures, system disk loads, and SSD temperatures.

---

## Storage temperature mapping

The public manifests use documentation-only endpoint addresses. Ignored local
copies preserve the deployed endpoints and dashboard instance selections.
The rules resolve sensor drivers through `node_hwmon_chip_names` rather than
publishing hardware paths or device identity.

Alerts match the driver name instead of assuming that PCI device paths start
with `k10temp`. The dashboard also joins driver names for readable legends and
shows CPU and GPU temperatures. The previous Apple SMC exclusion is removed.
The existing 85°C CPU / 75°C SSD thresholds and NVMe hotspot exception remain.
The [node exporter hwmon collector source](https://github.com/prometheus/node_exporter/blob/master/collector/hwmon_linux.go)
and [Prometheus vector matching documentation](https://prometheus.io/docs/prometheus/latest/querying/operators/#vector-matching)
describe the metadata and join used here.

Use `thermal-alerts-all.yaml` as the canonical alert manifest;
`thermal-alerts.yaml` is a compatibility copy defining the same resource and
must stay synchronized. Deploy one of them. The Kubernetes Grafana sidecar uses
`thermal-dashboard-configmap.yaml`; `thermal-dashboard.yaml` contains the
corresponding Grafana dashboard export.

The current exporter exposes CPU/GPU temperatures but no disk temperature
series for Unraid. These thermal rules do not establish Unraid drive health;
consult the ignored `cluster_status_export/03-storage.local.md` report for disk
assignments and pool status.

## 🛠️ Deploying & Testing Alerts

### Provision the Discord webhook

The Alertmanager manifest reads the webhook from the Kubernetes Secret
`discord-webhook-secret`; the URL must stay outside Git. Create the ignored
local file and replace its placeholder with a newly rotated Discord webhook:

```bash
cp secrets.local.env.example secrets.local.env
chmod 600 secrets.local.env
```

Load the value, create or update the Secret declaratively, then clear the shell
variable:

```bash
set -a
. ./secrets.local.env
set +a
kubectl -n monitoring create secret generic discord-webhook-secret \
  --from-literal=url="$DISCORD_WEBHOOK_URL" \
  --dry-run=client -o yaml | kubectl apply -f -
unset DISCORD_WEBHOOK_URL
```

The generated manifest is sent directly to the cluster and must not be saved
inside the repository.

### Apply Rules & Monitors
Copy the example-address manifests to ignored `.local.yaml` files and replace
their endpoints and ingress hosts. To deploy or update the local resources:
```bash
kubectl apply -f thermal-alerts-all.yaml -n monitoring
kubectl apply -f alertmanager-config.yaml -n monitoring
kubectl apply -f proxmox-monitor.local.yaml -n monitoring
kubectl apply -f unraid-monitor.local.yaml -n monitoring
kubectl apply -f grafana-ingress.local.yaml -n monitoring
kubectl apply -f prometheus-ingress.local.yaml -n monitoring
kubectl apply -f thermal-dashboard-configmap.yaml -n monitoring
```

### Trigger a Drill Test Alert
You can apply the test rule to verify that your Discord alerting pipeline and webhook secret are functioning properly:
```bash
kubectl apply -f test-alert.yaml -n monitoring
```
This forces a `ThermalTestAlert` to immediately fire. To resolve it, simply delete the resource:
```bash
kubectl delete -f test-alert.yaml -n monitoring
```
