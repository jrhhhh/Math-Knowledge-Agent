#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 BACKUP_DB" >&2
  exit 2
fi
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
db_path="${MATH_AGENT_DB_PATH:-$repo_dir/backend/math_agent.db}"
backup_path="$1"
if [[ ! -f "$backup_path" ]]; then
  echo "backup not found: $backup_path" >&2
  exit 1
fi
sqlite3 "$backup_path" "PRAGMA integrity_check;" | grep -qx ok
sqlite3 "$backup_path" ".backup '$db_path'"
echo "restored $db_path"
