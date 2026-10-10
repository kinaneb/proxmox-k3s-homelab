# Guide: Hypervisor SSD Thermal Pad Maintenance

This guide uses documentation-only names and addresses. Substitute values from
the ignored local inventory before safely shutting down a hypervisor to service
its storage SSD.

---

## Pre-requisites & Quorum Considerations
* `hypervisor-1` hosts the virtual machines `control-1` and `worker-1`.
* Because your K3s cluster has **3 Master nodes** in total, taking down `control-1` leaves 2 active Masters online. This satisfies the etcd consensus requirement (majority of 2 out of 3), meaning the cluster control plane will remain fully operational during maintenance.

---

## 🛠️ Step-by-Step Procedure

### Step 1: Evacuate (Drain) the K3s Nodes
Run these commands from your local workstation (where `kubectl` is configured) to migrate active workloads (like Kasm and Yaws app) gracefully to the remaining cluster nodes:
```bash
# Evacuate worker-1
kubectl drain worker-1 --ignore-daemonsets --delete-emptydir-data

# Evacuate control-1
kubectl drain control-1 --ignore-daemonsets --delete-emptydir-data
```

### Step 2: Gracefully Shut Down the Virtual Machines
SSH into the hypervisor and gracefully power off the guest VMs. The example
worker VMID is `9101` and the control-plane VMID is `9001`:
```bash
ssh root@192.0.2.21 "qm stop 9101 && qm stop 9001"
```
*(Verify they are stopped by running `qm list` on the host).*

### Step 3: Shut Down the Proxmox Host
Once the virtual machines have shut down, run the poweroff command on the physical host:
```bash
ssh root@192.0.2.21 "poweroff"
```
Wait for the physical machine's fans and power lights to turn off completely.

### Step 4: Perform Physical Maintenance
1. **Unplug the power cable** from the hypervisor chassis.
2. Slide open the metal case and locate the M.2 SSD slot on the underside of the motherboard.
3. Gently wipe the SSD controller and NAND packages with a dry microfiber cloth.
4. Cut and place a **1.5mm thermal pad** (e.g., Gelid GP-Extreme or Thermal Grizzly Minus Pad 8) directly over the SSD chips.
5. Re-assemble the metal case bottom cover (it will press slightly against the pad, transferring heat directly to the steel chassis).
6. Plug the power cable back in and power the system on.

### Step 5: Uncordon the Nodes
Once the hypervisor boots, Proxmox will automatically start the control-plane
and worker VMs.
After about 3–5 minutes, verify that the nodes are back online from your local workstation:
```bash
kubectl get nodes
```
They will initially show as `Ready,SchedulingDisabled`. Re-enable scheduling to allow workloads to run on them again:
```bash
kubectl uncordon worker-1
kubectl uncordon control-1
```
The cluster will automatically begin rebalancing workloads back to `hypervisor-1`.
