#!/bin/bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_PATH="/Applications/Commander One.app"
SOURCE_LPROJ_PATH="$SCRIPT_DIR/zh-Hans.lproj"
FORCE=0
BACKUP_LPROJ_PATH=""

usage() {
  cat <<'EOF'
usage: update-translation.sh [--app PATH] [--backup-lproj PATH] [--force]

Apply only the zh-Hans translation to an existing Commander One.app and
re-sign the app afterwards.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app)
      APP_PATH="$2"
      shift 2
      ;;
    --backup-lproj)
      BACKUP_LPROJ_PATH="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -d "$APP_PATH" ]]; then
  echo "source app not found: $APP_PATH" >&2
  exit 1
fi

if [[ ! -d "$SOURCE_LPROJ_PATH" ]]; then
  echo "translation source not found: $SOURCE_LPROJ_PATH" >&2
  exit 1
fi

if pgrep -x "Commander One" >/dev/null 2>&1; then
  echo "Commander One is currently running. Close it first." >&2
  exit 1
fi

TARGET_LPROJ_PATH="$APP_PATH/Contents/Resources/zh-Hans.lproj"
if [[ -z "$BACKUP_LPROJ_PATH" ]]; then
  BACKUP_LPROJ_PATH="${TARGET_LPROJ_PATH}.backup-$(date +%Y%m%d-%H%M%S)"
fi

if [[ -e "$BACKUP_LPROJ_PATH" ]]; then
  if [[ "$FORCE" -ne 1 ]]; then
    echo "backup path already exists: $BACKUP_LPROJ_PATH" >&2
    echo "rerun with --force to overwrite it" >&2
    exit 1
  fi
  rm -rf "$BACKUP_LPROJ_PATH"
fi

if [[ -d "$TARGET_LPROJ_PATH" ]]; then
  mv "$TARGET_LPROJ_PATH" "$BACKUP_LPROJ_PATH"
fi

ditto "$SOURCE_LPROJ_PATH" "$TARGET_LPROJ_PATH"
codesign --force --deep --sign - --timestamp=none "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

echo "translation updated:"
echo "  app:    $APP_PATH"
if [[ -d "$BACKUP_LPROJ_PATH" ]]; then
  echo "  backup: $BACKUP_LPROJ_PATH"
fi

