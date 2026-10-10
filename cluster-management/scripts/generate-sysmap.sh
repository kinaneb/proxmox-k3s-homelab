#!/usr/bin/env bash
# scripts/generate-sysmap.sh - Homelab Infrastructure State Exporter
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
export ANSIBLE_CONFIG="$PROJECT_DIR/ansible.cfg"
OUTPUT_DIR="$PROJECT_DIR/../cluster_status_export"
INVENTORY_FILE="$PROJECT_DIR/inventory/hosts.local.ini"
for dependency in ansible kubectl; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "Required command missing: $dependency" >&2
        exit 1
    fi
done
mkdir -p "$OUTPUT_DIR"
FINAL_OUTPUT_DIR="$OUTPUT_DIR"
OUTPUT_DIR="$(mktemp -d "$FINAL_OUTPUT_DIR/.sysmap.XXXXXX")"
trap 'rm -rf -- "$OUTPUT_DIR"' EXIT
GENERATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# pipefail propagates query failures through formatting pipelines. With set -e,
# any failure exits before publishing, preserving the previous exports.


echo "================================================================="
echo "🚀 Starting Multi-Auth Homelab Discovery Loop"
echo "================================================================="

# 1. K3S KUBERNETES LAYER EXTRACTION (Local context via Workstation)
    echo "📦 Extracting K3s Topology and Runtime State..."
    printf "<!-- Generated at %s -->\n\n" "$GENERATED_AT" > "$OUTPUT_DIR/02-cluster.local.md"
    kubectl --request-timeout=30s get nodes -o wide >> "$OUTPUT_DIR/02-cluster.local.md"
    echo -e "\n### LIVE POD MATRIX\n" >> "$OUTPUT_DIR/02-cluster.local.md"
    kubectl --request-timeout=30s get pods -A -o wide >> "$OUTPUT_DIR/02-cluster.local.md"
    echo -e "\n### NETWORK ROUTING & INGRESS MATRIX\n" >> "$OUTPUT_DIR/02-cluster.local.md"
    kubectl --request-timeout=30s get svc,ingress -A >> "$OUTPUT_DIR/02-cluster.local.md"

# 2. PROXMOX HYPERVISOR LAYER EXTRACTION
echo "🔮 Querying Proxmox Bare-Metal Layer via Scoped Inventory..."
{
    printf "<!-- Generated at %s -->\n\n" "$GENERATED_AT"
    echo "# PROXMOX INVENTORY STATE"
    echo ""
    for node in $(ansible proxmox -i "$INVENTORY_FILE" --list-hosts | sed '1d'); do
        echo "## Host Identity: $node"
        echo "### Network Interfaces"
        ansible "$node" -i "$INVENTORY_FILE" -m shell -a "cat /etc/network/interfaces" | sed 's/^/    /'
        echo "### Virtual Machine Inventory"
        ansible "$node" -i "$INVENTORY_FILE" -m shell -a "qm list" | sed 's/^/    /'
        echo "### Storage Pool Status"
        ansible "$node" -i "$INVENTORY_FILE" -m shell -a "pvesm status" | sed 's/^/    /'
        echo ""
    done
} > "$OUTPUT_DIR/01-infrastructure.local.md"

# 3. UNRAID STORAGE SUBSYSTEM LAYER EXTRACTION
echo "💾 Querying Unraid Storage Array..."
{
    printf "<!-- Generated at %s -->\n\n" "$GENERATED_AT"
    echo "# UNRAID DATA SERVER"
    echo ""
    # Query the installed hardware instead of assuming the previous chassis.
    # raw works on Unraid without requiring a remote Python interpreter.
    echo "## Hardware Identity & Operating System"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a '
        set -eu
        for field in sys_vendor product_name product_version board_name bios_version bios_date; do
            printf "%s=" "$field"
            cat "/sys/class/dmi/id/$field"
        done
        hostname
        cat /etc/unraid-version
        uname -r
    ' | sed 's/^/    /'
    echo "## CPU & Memory"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a '
        set -eu
        lscpu
        grep "^MemTotal:" /proc/meminfo
        memory_info=$(dmidecode --type 17)
        printf "%s\n" "$memory_info" | sed -n "/^[[:space:]]*Size:/p; /^[[:space:]]*Locator:/p; /^[[:space:]]*Type:/p; /^[[:space:]]*Configured Memory Speed:/p"
    ' | sed 's/^/    /'
    echo "## Network Interfaces & Routes"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a 'set -eu; ip -brief address; ip route' | sed 's/^/    /'
    echo "## Hardware Sensors"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a 'if command -v sensors >/dev/null 2>&1; then sensors; else echo "Unavailable: sensors is not installed"; fi' | sed 's/^/    /'
    echo "## Disk Assignments & Array Health"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a "mdcmd status" | sed 's/^/    /'
    echo "## Block Device Layout"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a "lsblk -o NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT,UUID" | sed 's/^/    /'
    echo "## ZFS Pools & Datasets"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a 'set -eu; if command -v zpool >/dev/null 2>&1; then zpool list; zfs list -o name,used,avail,mountpoint; else echo "Unavailable: ZFS tools are not installed"; fi' | sed 's/^/    /'
    echo "## NFS Export Definitions"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a "cat /etc/exports" | sed 's/^/    /'
    echo "## SMB Share Layout"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a 'set -eu; shares=$(cat /etc/samba/smb-shares.conf); if [ -n "$shares" ]; then printf "%s\n" "$shares"; else echo "No SMB shares configured in /etc/samba/smb-shares.conf"; fi' | sed 's/^/    /'
    echo "## Native Docker Engine State"
    ansible unraid -i "$INVENTORY_FILE" -m raw -a "docker ps --format 'table {% raw %}{{.Names}}\t{{.Image}}\t{{.Ports}}{% endraw %}'" | sed 's/^/    /'
} > "$OUTPUT_DIR/03-storage.local.md"
echo "================================================================="
for report in 01-infrastructure.local.md 02-cluster.local.md 03-storage.local.md; do
    mv -- "$OUTPUT_DIR/$report" "$FINAL_OUTPUT_DIR/$report"
done
echo "✅ Discovery Matrix Populated Successfully! ($GENERATED_AT)"
echo "================================================================="
