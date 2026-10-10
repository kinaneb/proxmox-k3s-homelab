# Repository secret handling

Secret values do not belong in tracked YAML, source code, examples, comments,
or generated cluster exports. A comment is still part of Git history.

## Supported patterns

- Ansible secrets: use an encrypted Ansible Vault file, or a `secrets.local.yml`
  file covered by `.gitignore`. Commit a placeholder `*.example` file.
- Kubernetes workloads: commit only a `secretKeyRef` or operator-managed secret
  reference. Provision the actual Secret from an ignored local file or an
  encrypted GitOps controller such as SOPS with age.
- Local applications: use an ignored `.env` file and commit `.env.example`.
- CI: store values in Forgejo Actions secrets and reference them with the
  platform's `secrets.NAME` expression.
- Site identity: keep addresses, hostnames, domains, hardware identifiers,
  storage paths, and generated runtime state in ignored `*.local.*` files.
  Commit only `.example` files using RFC 5737 addresses and `example.invalid`.

Run the repository check before every commit:

```bash
./scripts/check-secrets.sh
```

## Before making the repository public

Removing a value from the latest commit does not remove it from Git history.
Rotate every credential that has ever been committed, then either rewrite all
published refs with `git filter-repo` or publish a clean, history-free snapshot
to a new public repository. Rewriting shared history requires every clone to be
recreated or carefully rebased.

For this repository, rotate at least:

1. the K3s cluster join token;
2. the Discord Alertmanager webhook URL.
3. the Forgejo runner registration token.

Do not make the existing remote public until rotation and history cleanup are
complete.
