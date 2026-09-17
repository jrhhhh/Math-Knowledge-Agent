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
result="$(sqlite3 "$backup_path" 'PRAGMA integrity_check;')"
if [[ "$result" != "ok" ]]; then
  echo "backup integrity check failed: $result" >&2
  exit 1
fi
echo "backup healthy: $backup_path"
