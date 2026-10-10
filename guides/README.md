# Homelab Operations Guides

This directory contains step-by-step guides for physical hardware maintenance, troubleshooting, and operations across your homelab environment.

---

## 📂 Available Guides

*   **[hypervisor-1 SSD Thermal Pad Maintenance](hypervisor-ssd-maintenance.md)**: Steps to safely drain, shut down, apply a thermal pad to the storage SSD on the hypervisor chassis, and bring the nodes back online.
*   **[Proxmox LVM Thinpool Optimization & TRIM](proxmox-thinpool-optimization.md)**: Procedure for configuring SCSI `discard=on`, executing rolling VM reboots, running guest `fstrim`, and reclaiming LVM thinpool storage.
*   **[Longhorn Disk UUID Mismatch Repair](longhorn-uuid-mismatch-repair.md)**: Steps for diagnosing and resolving `DiskFilesystemChanged` / `diskUUID` mismatch errors without replica data loss.
