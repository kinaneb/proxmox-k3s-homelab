#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
cd "$repository_root"

failed=0

report_paths() {
  local heading="$1"
  local paths="$2"

  if [[ -n "$paths" ]]; then
    printf '%s\n%s\n' "$heading" "$paths" >&2
    failed=1
  fi
}

# Keep real credential containers out of Git. Examples and encrypted Ansible
# Vault files are intentionally allowed.
sensitive_paths="$({
  git ls-files | grep -E '(^|/)(\.env|id_(rsa|ed25519)|kubeconfig)(\.|$)|(^|/).*(client_secret|credentials).*\.json$|\.(pem|p12|pfx)$' || true
} | grep -Ev '(^|/)(\.env\.example|.*\.example)$' || true)"
report_paths "Tracked credential-shaped files:" "$sensitive_paths"

# Match provider tokens, private keys, and webhook URLs. Only filenames are
# printed so the scanner itself never repeats a credential in logs.
signature_regex='AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,}|xox[baprs]-[0-9A-Za-z-]{10,}|sk-[0-9A-Za-z_-]{20,}|-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----|https://(discord(app)?\.com/api/webhooks|hooks\.slack\.com/services|api\.telegram\.org/bot)|Bearer[[:space:]]+[0-9A-Za-z._~+/-]{16,}|--token[[:space:]]+[0-9A-Za-z_-]{20,}'
signature_paths="$(git grep -Il -E "$signature_regex" -- . \
  ':!temperature-monitoring/kube-prometheus-stack/**' \
  ':!scripts/check-secrets.sh' || true)"
report_paths "Files containing credential signatures:" "$signature_paths"

# Catch long literal values assigned to common secret variable names. Template
# references, examples, tests, and obvious placeholders are filtered out.
assignment_regex="^[[:space:]#-]*[A-Za-z0-9_.-]*(password|passwd|token|api[_-]?key|client[_-]?secret|webhook[_-]?url)[A-Za-z0-9_.-]*[[:space:]]*[:=][[:space:]]*[\"']?[A-Za-z0-9_./+=:@-]{16,}"
assignment_paths="$({
  git grep -nI -E "$assignment_regex" -- . \
    ':!temperature-monitoring/kube-prometheus-stack/**' \
    ':!**/*example*' \
    ':!**/test_*' \
    ':!scripts/check-secrets.sh' \
    ':!cluster-management/inventory/group_vars/k3s_cluster/vault.yml' || true
} | grep -Eiv '(replace|example|placeholder|dummy|changeme)' | cut -d: -f1 | sort -u || true)"
report_paths "Files containing possible literal secret assignments:" "$assignment_paths"

# Site identity is private even when it is not an authentication credential.
# Examples use RFC 5737 addresses and example.invalid names, so real private
# ranges, local DNS suffixes, hardware addresses, and workstation paths fail.
privacy_regex='(^|[^0-9])(10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)|([A-Za-z0-9-]+\.)+(local|home\.arpa|ts\.net)([/:[:space:]]|$)|([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|/Users/[^/[:space:]]+|/home/[^/[:space:]]+'
privacy_paths="$(git grep -Il -E "$privacy_regex" -- . \
  ':!temperature-monitoring/kube-prometheus-stack/**' \
  ':!**/*example*' \
  ':!scripts/check-secrets.sh' || true)"
report_paths "Files containing private site identity:" "$privacy_paths"

if (( failed != 0 )); then
  printf '%s\n' "Secret scan failed. Move values to an ignored local file or Ansible Vault." >&2
  exit 1
fi

printf '%s\n' "Secret scan passed."
