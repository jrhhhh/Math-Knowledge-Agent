#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 BACKUP_DB" >&2
  exit 2
fi
backup_path="$1"
if [[ ! -f "$backup_path" ]]; then
  echo "backup not found: $backup_path" >&2
  exit 1
fi
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
restored_path="$tmp_dir/restored.db"
sqlite3 "$backup_path" ".backup '$restored_path'"
[[ "$(sqlite3 "$restored_path" 'PRAGMA integrity_check;')" == "ok" ]]
for table in concepts problems concept_relations; do
  sqlite3 "$restored_path" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='$table';" | grep -qx 1
done
echo "restore rehearsal passed: $backup_path"
