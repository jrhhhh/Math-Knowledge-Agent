#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log_file="${MATH_AGENT_BACKUP_LOG:-/tmp/math-agent-backup.log}"
status_file="${MATH_AGENT_BACKUP_STATUS_FILE:-$repo_dir/backups/backup-status.json}"
webhook="${MATH_AGENT_ALERT_WEBHOOK:-}"
mkdir -p "$(dirname "$status_file")"

if backup_path="$($repo_dir/scripts/backup_db.sh 2>>"$log_file")" \
  && "$repo_dir/scripts/check_backup.sh" "$backup_path" >>"$log_file" 2>&1 \
  && "$repo_dir/scripts/rehearse_restore.sh" "$backup_path" >>"$log_file" 2>&1; then
  printf '{"status":"succeeded","timestamp":%s,"backup_path":"%s"}\n' "$(date +%s)" "$backup_path" > "$status_file"
  exit 0
fi

printf '{"status":"failed","timestamp":%s}\n' "$(date +%s)" > "$status_file"

if [[ -n "$webhook" ]] && command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error --max-time 5 -X POST "$webhook" \
    -H 'Content-Type: application/json' \
    --data '{"text":"Math Agent 自动备份失败，请检查备份日志。"}' >>"$log_file" 2>&1 || true
fi
echo "backup job failed; see $log_file" >&2
exit 1
