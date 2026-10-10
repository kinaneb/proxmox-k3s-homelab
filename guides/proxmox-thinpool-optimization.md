# Guide: Proxmox LVM Thinpool Optimization & Guest TRIM

This guide describes the complete procedure for configuring SCSI discard (`discard=on`), executing guest-level TRIM (`fstrim`), and automating storage reclamation across Proxmox VE hypervisors (`hypervisor-1`, `hypervisor-2`, `hypervisor-3`) and K3s virtual machine nodes.

---

## 💡 Technical Principles

1. **LVM Thin Provisioning Behavior**:
   * Proxmox `local-lvm` (`pve/data`) allocates storage blocks dynamically on demand.
   * When files or container images are deleted inside a guest VM, the Linux filesystem frees the blocks internally, but Proxmox thinpool storage does **not** automatically shrink unless `fstrim` / SCSI UNMAP calls are passed to the hypervisor.
2. **QEMU `discard=on` Requirement**:
   * Proxmox virtual SCSI controllers must have `,discard=on` enabled for QEMU to translate guest `fstrim` calls into LVM thinpool block de-allocations.
3. **QEMU Driver Initialization**:
   * Adding `,discard=on` to a running VM takes effect immediately in Proxmox configuration, but the underlying QEMU process must be restarted (`qm reboot <VMID>`) to attach UNMAP ioctls to the active block driver.

---

## 🛠️ Step-by-Step Optimization Procedure

### Step 1: Enable `discard=on` Across Proxmox Virtual Machines

Connect to each Proxmox node and update the SCSI disk configuration for your virtual machines:

```bash
# hypervisor-1 (192.0.2.21) - control-1 (VM 9001) & worker-1 (VM 9101)
ssh root@192.0.2.21 "qm set 9001 -scsi0 local-lvm:vm-9001-disk-0,discard=on,iothread=1"
ssh root@192.0.2.21 "qm set 9101 -scsi0 local-lvm:vm-9101-disk-0,discard=on,iothread=1"

# hypervisor-2 (192.0.2.22) - control-2 (VM 9002) & worker-2 (VM 9102)
ssh root@192.0.2.22 "qm set 9002 -scsi0 local-lvm:vm-9002-disk-0,discard=on,iothread=1"
ssh root@192.0.2.22 "qm set 9102 -scsi0 local-lvm:vm-9102-disk-0,discard=on,iothread=1"

# hypervisor-3 (192.0.2.23) - control-3 (VM 9003) & worker-3 (VM 9103)
ssh root@192.0.2.23 "qm set 9003 -scsi0 local-lvm:vm-9003-disk-0,discard=on,iothread=1"
ssh root@192.0.2.23 "qm set 9103 -scsi0 local-lvm:vm-9103-disk-0,discard=on,iothread=1"
```

---

### Step 2: Perform Rolling VM Node Reboots

To load the updated SCSI driver cleanly without cluster downtime, reboot nodes one at a time and verify node health before moving to the next:

```bash
# 1. Reboot Control Plane Node (e.g. control-1 on hypervisor-1)
ssh root@192.0.2.21 "qm reboot 9001"

# Wait for control-1 to return to Ready status
kubectl get node control-1 -w

# 2. Reboot Worker Node (e.g. worker-1 on hypervisor-1)
ssh root@192.0.2.21 "qm reboot 9101"

# Wait for worker-1 to return to Ready status
kubectl get node worker-1 -w
```
*(Repeat the rolling reboot sequence for `hypervisor-2` and `hypervisor-3`).*

---

### Step 3: Execute `fstrim` Inside Guest VMs

Once a node is back online, execute `fstrim -v /` inside the VM guest via the QEMU Guest Agent:

```bash
# Trim control-1 & worker-1 on hypervisor-1
ssh root@192.0.2.21 "qm guest exec 9001 -- fstrim -v /"
ssh root@192.0.2.21 "qm guest exec 9101 -- fstrim -v /"

# Trim control-2 & worker-2 on hypervisor-2
ssh root@192.0.2.22 "qm guest exec 9002 -- fstrim -v /"
ssh root@192.0.2.22 "qm guest exec 9102 -- fstrim -v /"

# Trim control-3 & worker-3 on hypervisor-3
ssh root@192.0.2.23 "qm guest exec 9003 -- fstrim -v /"
ssh root@192.0.2.23 "qm guest exec 9103 -- fstrim -v /"
```

---

### Step 4: Verify Reclaimed Storage Space

Query the LVM logical volume status on each hypervisor to confirm space reclamation:

```bash
ssh root@192.0.2.21 "lvs -a -o lv_name,vg_name,lv_size,data_percent,metadata_percent"
ssh root@192.0.2.22 "lvs -a -o lv_name,vg_name,lv_size,data_percent,metadata_percent"
ssh root@192.0.2.23 "lvs -a -o lv_name,vg_name,lv_size,data_percent,metadata_percent"
```

---

## 🤖 Automated Host Maintenance (Ansible)

Ensure automated host tuning is enabled across all hypervisors by running the Ansible playbook:

```bash
ansible-playbook -i cluster-management/inventory/hosts.local.ini cluster-management/playbooks/pve-host-tuning.yaml
```

This ensures `fstrim.timer` is enabled and configures auto-extend thresholds (`thin_pool_autoextend_threshold = 80`) in `/etc/lvm/lvm.conf`.
