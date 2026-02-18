#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SECRETS_DIR="${SECRETS_DIR:-$ROOT_DIR/secrets}"
HEALTH_URL="${SMOKE_HEALTH_URL:-http://127.0.0.1:9754/healthz}"
METRICS_URL="${SMOKE_METRICS_URL:-http://127.0.0.1:9754/metrics}"
RETRY_COUNT="${ROTATE_CHECK_RETRY_COUNT:-30}"
RETRY_INTERVAL="${ROTATE_CHECK_RETRY_INTERVAL_SECONDS:-2}"

KEY_FILE="$SECRETS_DIR/gmo_api_key"
SECRET_FILE="$SECRETS_DIR/gmo_api_secret"
WEBHOOK_FILE="$SECRETS_DIR/discord_webhook_url"

TMP_DIR="$(mktemp -d)"
BACKUP_DIR="$TMP_DIR/original"
mkdir -p "$BACKUP_DIR"

save_original() {
  local source="$1"
  local dest="$2"
  if [[ -f "$source" ]]; then
    cp "$source" "$dest"
  fi
}

restore_original() {
  local source="$1"
  local backup="$2"
  if [[ -f "$backup" ]]; then
    cp "$backup" "$source"
  else
    rm -f "$source"
  fi
}

cleanup() {
  restore_original "$KEY_FILE" "$BACKUP_DIR/gmo_api_key"
  restore_original "$SECRET_FILE" "$BACKUP_DIR/gmo_api_secret"
  restore_original "$WEBHOOK_FILE" "$BACKUP_DIR/discord_webhook_url"
  docker-compose down >/dev/null 2>&1 || true
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

save_original "$KEY_FILE" "$BACKUP_DIR/gmo_api_key"
save_original "$SECRET_FILE" "$BACKUP_DIR/gmo_api_secret"
save_original "$WEBHOOK_FILE" "$BACKUP_DIR/discord_webhook_url"

mkdir -p "$SECRETS_DIR"

ensure_writable_secrets_dir() {
  if [[ -w "$SECRETS_DIR" ]]; then
    return 0
  fi

  echo "[rotate-secrets] INFO: fixing secrets directory ownership"
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    alpine:3.20 \
    sh -lc "chown -R $(id -u):$(id -g) /workspace/secrets" >/dev/null

  if [[ ! -w "$SECRETS_DIR" ]]; then
    echo "[rotate-secrets] FAIL: secrets_directory_not_writable ($SECRETS_DIR)"
    return 1
  fi
}

ensure_writable_secrets_dir

write_secret_set() {
  local phase="$1"
  printf '%s' "${phase}_demo_gmo_api_key" > "$KEY_FILE"
  printf '%s' "${phase}_demo_gmo_api_secret" > "$SECRET_FILE"
  printf '%s' "${phase}_demo_discord_webhook_url" > "$WEBHOOK_FILE"
  chmod 600 "$KEY_FILE" "$SECRET_FILE" "$WEBHOOK_FILE"
}

wait_for_health() {
  for _ in $(seq 1 "$RETRY_COUNT"); do
    if curl -fsS "$HEALTH_URL" >/dev/null; then
      return 0
    fi
    sleep "$RETRY_INTERVAL"
  done
  return 1
}

check_stage() {
  local stage="$1"

  echo "[rotate-secrets] START: ${stage}"
  docker-compose down --remove-orphans >/dev/null 2>&1 || true
  docker-compose up -d --build bot

  if ! wait_for_health; then
    echo "[rotate-secrets] FAIL: ${stage} (healthz_unreachable)"
    docker-compose ps || true
    docker-compose logs --tail=200 bot || true
    return 1
  fi

  if ! curl -fsS "$METRICS_URL" >/dev/null; then
    echo "[rotate-secrets] FAIL: ${stage} (metrics_unreachable)"
    docker-compose ps || true
    docker-compose logs --tail=200 bot || true
    return 1
  fi

  if ! bash scripts/smoke_live_daemon.sh; then
    echo "[rotate-secrets] FAIL: ${stage} (smoke_failed)"
    return 1
  fi

  echo "[rotate-secrets] PASS: ${stage}"
}

echo "[rotate-secrets] INFO: starting rotation exercise (secret values are masked)"

write_secret_set "old"
check_stage "before_rotation"

write_secret_set "new"
check_stage "after_rotation"

echo "[rotate-secrets] SUCCESS: secret rotation exercise completed"
exit 0
