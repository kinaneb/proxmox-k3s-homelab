# Guide: Ansible SSH Key Setup (Passwordless Access to K3s Nodes)

This guide walks through setting up passwordless SSH authentication from your Mac
to all K3s nodes, so Ansible playbooks run without `-k` or passphrase prompts.

**When to follow this guide:**
- First-time setup of a new workstation
- After re-generating your `homelab` SSH key
- After rebuilding K3s VMs from scratch

---

## Background

The `homelab` key (`~/.ssh/homelab`) is used for **all SSH connections** in this homelab:
- `root@` on Proxmox hosts (`hypervisor-1`, `hypervisor-2`, `hypervisor-3`)
- `user@` on all K3s nodes (`control-1/2/3`, `worker-1/2/3`)

Ansible connects to K3s nodes via **ProxyJump** through their parent Proxmox host.
The `homelab` public key must be present in `user`'s `authorized_keys` on each VM.

---

## Step 1: Bootstrap — Deploy the SSH Key (Run Once)

This uses password authentication (`-k`) to connect and install the key.
You only ever need to run this once per workstation.

```bash
cd /path/to/ansible-pve-k3s/cluster-management
ansible-playbook playbooks/setup-ssh-keys.yaml --ask-vault-pass -k
```

Enter your **Vault password** and **SSH password** when prompted.
The playbook adds `~/.ssh/homelab.pub` to `user`'s `authorized_keys` on all 6 K3s VMs.

**Expected output:**
```
✅ homelab key deployed to user@control-1 (198.51.100.11)
✅ homelab key deployed to user@control-2 (198.51.100.12)
✅ homelab key deployed to user@control-3 (198.51.100.13)
✅ homelab key deployed to user@worker-1 (198.51.100.21)
✅ homelab key deployed to user@worker-2 (198.51.100.22)
✅ homelab key deployed to user@worker-3 (198.51.100.23)
```

---

## Step 2: Add Key to macOS Keychain (Never Type Passphrase Again)

The `homelab` key has a passphrase. Without this step, every Ansible run and
every `ssh control-1` would prompt for it. This stores it permanently in macOS Keychain:

```bash
ssh-add --apple-use-keychain ~/.ssh/homelab
```

Enter your passphrase **once**. macOS stores it and auto-loads the key on every login.

---

## Step 3: Verify Passwordless Access

Confirm all 6 nodes are reachable without any password prompt:

```bash
cd cluster-management
ansible all -m ping --limit k3s_cluster --ask-vault-pass
```

All nodes should return `pong` with only the Vault password asked (no SSH password, no passphrase).

---

## Step 4: Run Playbooks Without `-k`

You can now run all Ansible playbooks normally:

```bash
# Set up automatic nightly security patches
ansible-playbook playbooks/configure-unattended-upgrades.yaml --ask-vault-pass

# Apply a full rolling cluster patch
ansible-playbook playbooks/patch-cluster.yaml --ask-vault-pass
```

---

## Troubleshooting

### `Permission denied (publickey,password)` after key deployment

The `homelab` key is not in the SSH agent. Add it:
```bash
ssh-add --apple-use-keychain ~/.ssh/homelab
```

### `Enter passphrase for key` keeps appearing

The Keychain entry was lost (e.g. after a macOS upgrade). Re-add it:
```bash
ssh-add --apple-use-keychain ~/.ssh/homelab
```

### New VM was rebuilt — key is missing

Re-run Step 1 for the specific host only:
```bash
ansible-playbook playbooks/setup-ssh-keys.yaml --ask-vault-pass -k --limit control-1
```

### `UNREACHABLE` on a specific node

Check if the VM is running on its Proxmox host:
```bash
ssh root@192.0.2.22 "qm list"   # hypervisor-2
ssh root@192.0.2.23 "qm list"   # hypervisor-3
ssh root@192.0.2.21 "qm list"   # hypervisor-1
```

---

## Reference: SSH Key Map

| Key | Used For | Auth User |
|-----|----------|-----------|
| `~/.ssh/homelab` | Proxmox hosts (hypervisor-1/2/3) | `root` |
| `~/.ssh/homelab` | K3s VMs (all masters + workers) | `user` |
