#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
db_path="${MATH_AGENT_DB_PATH:-$repo_dir/backend/math_agent.db}"
backup_dir="${MATH_AGENT_BACKUP_DIR:-$repo_dir/backups}"
mkdir -p "$backup_dir"
if [[ ! -f "$db_path" ]]; then
  echo "database not found: $db_path" >&2
  exit 1
fi
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_path="$backup_dir/math_agent-$timestamp.db"
sqlite3 "$db_path" ".backup '$backup_path'"
echo "$backup_path"
