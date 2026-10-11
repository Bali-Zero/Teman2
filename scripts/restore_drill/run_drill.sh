#!/bin/bash
# Monthly Mini restore drill: newest Tigris dump -> throwaway PostGIS -> Level-5 verifier.
# Never print restore.log: SQL errors can include production row values (client PII).

set -euo pipefail
umask 077

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
CONTAINER_NAME="${RESTORE_DRILL_CONTAINER:-nuzantara-pg-drill}"
IMAGE="${RESTORE_DRILL_IMAGE:-nuzantara/pg-drill:17-postgis}"
DRILL_PORT="${DRILL_PORT:-15499}"
DRILL_USER="${DRILL_USER:-drill}"
DRILL_PASSWORD="${DRILL_PASSWORD:-drill}"
DRILL_DB="${DRILL_DB:-nuzantara_drill}"
TIGRIS_ENDPOINT="${TIGRIS_ENDPOINT:-https://fly.storage.tigris.dev}"
TIGRIS_BUCKET="${TIGRIS_BUCKET:-nuzantara-backups}"
TIMEOUT_SECONDS="${RESTORE_DRILL_TIMEOUT_SECONDS:-1800}"
MIN_VM_FREE_KB="${RESTORE_DRILL_MIN_VM_FREE_KB:-8388608}"
WORK_DIR=$(mktemp -d /tmp/nuzantara-restore-drill.XXXXXX)
WATCHDOG_PID=""

cleanup() {
    rc=$?
    trap - EXIT INT TERM
    if [ -n "$WATCHDOG_PID" ]; then
        kill "$WATCHDOG_PID" 2>/dev/null || true
    fi
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    rm -rf "$WORK_DIR"
    exit "$rc"
}
trap cleanup EXIT INT TERM

cannot_verify() {
    echo "CANNOT-VERIFY: $*" >&2
    exit 2
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || cannot_verify "required command missing: $1"
}

sha256_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        cannot_verify "no SHA-256 utility available"
    fi
}

check_vm_disk_floor() {
    local df_output free_kb
    df_output=$(colima ssh -- df -Pk / 2>/dev/null) \
        || cannot_verify "cannot measure free disk in the Colima VM"
    free_kb=$(printf '%s\n' "$df_output" | awk 'NR > 1 && $NF == "/" {print $4; exit}')
    case "$free_kb" in
        ''|*[!0-9]*) cannot_verify "Colima VM free-disk measurement was not numeric" ;;
    esac
    if [ "$free_kb" -lt "$MIN_VM_FREE_KB" ]; then
        cannot_verify "Colima VM has less than 8 GiB free"
    fi
}

ensure_image() {
    local dockerfile_hash current_hash
    dockerfile_hash=$(sha256_file "$SCRIPT_DIR/Dockerfile")
    current_hash=$(docker image inspect "$IMAGE" \
        --format '{{index .Config.Labels "nuzantara.dockerfile.sha256"}}' 2>/dev/null || true)
    if [ "$current_hash" = "$dockerfile_hash" ]; then
        echo "Restore image cache is current"
        return
    fi
    echo "Building restore image because the Dockerfile changed or the image is absent"
    docker build --build-arg "DOCKERFILE_SHA=$dockerfile_hash" \
        --tag "$IMAGE" "$SCRIPT_DIR"
}

wait_for_postgres() {
    local attempt health
    attempt=0
    while [ "$attempt" -lt 60 ]; do
        health=$(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)
        [ "$health" = "healthy" ] && return 0
        sleep 2
        attempt=$((attempt + 1))
    done
    cannot_verify "throwaway Postgres did not become healthy"
}

drill_main() {
    # The worker owns no cleanup trap; the parent always removes the container and private tmpdir.
    trap - EXIT INT TERM
    require_command aws
    require_command colima
    require_command docker
    require_command gunzip
    require_command psql
    require_command python3

    [ -n "${AWS_ACCESS_KEY_ID:-}" ] || cannot_verify "AWS_ACCESS_KEY_ID is not configured"
    [ -n "${AWS_SECRET_ACCESS_KEY:-}" ] || cannot_verify "AWS_SECRET_ACCESS_KEY is not configured"
    docker info >/dev/null 2>&1 || cannot_verify "Docker/Colima is unavailable"
    check_vm_disk_floor
    ensure_image

    local listing latest dump_path dump_bytes dsn roles_sql restore_log
    listing=$(aws --endpoint-url "$TIGRIS_ENDPOINT" s3 ls \
        "s3://$TIGRIS_BUCKET/postgres/") \
        || cannot_verify "cannot list Tigris postgres backups"
    latest=$(printf '%s\n' "$listing" | awk '{print $4}' \
        | grep -E '\.sql\.gz$' | sort | tail -1 || true)
    [ -n "$latest" ] || cannot_verify "no compressed SQL backup found"

    dump_path="$WORK_DIR/$latest"
    aws --endpoint-url "$TIGRIS_ENDPOINT" s3 cp \
        "s3://$TIGRIS_BUCKET/postgres/$latest" "$dump_path" \
        || cannot_verify "cannot download newest Tigris backup"
    dump_bytes=$(wc -c < "$dump_path" | tr -d ' ')
    case "$dump_bytes" in
        ''|*[!0-9]*) cannot_verify "downloaded backup size was not numeric" ;;
    esac
    [ "$dump_bytes" -gt 1000000 ] || cannot_verify "downloaded backup is unexpectedly small"

    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker run --rm --detach --name "$CONTAINER_NAME" \
        --publish "127.0.0.1:${DRILL_PORT}:5432" \
        --env "POSTGRES_USER=$DRILL_USER" \
        --env "POSTGRES_PASSWORD=$DRILL_PASSWORD" \
        --env "POSTGRES_DB=$DRILL_DB" \
        --health-cmd "pg_isready -U $DRILL_USER -d $DRILL_DB" \
        --health-interval 5s --health-timeout 5s --health-retries 20 \
        "$IMAGE" >/dev/null
    wait_for_postgres

    dsn="postgresql://${DRILL_USER}:${DRILL_PASSWORD}@127.0.0.1:${DRILL_PORT}/${DRILL_DB}"
    roles_sql="$WORK_DIR/roles.sql"
    python3 "$SCRIPT_DIR/role_scanner.py" "$dump_path" \
        --exclude "$DRILL_USER" --output "$roles_sql" \
        || cannot_verify "role derivation from the dump failed"
    psql "$dsn" -v ON_ERROR_STOP=1 -f "$roles_sql" >/dev/null \
        || cannot_verify "role pre-create failed"

    restore_log="$WORK_DIR/restore.log"
    # Keep ON_ERROR_STOP=1: weakening the restore would recreate the blind spot this drill closes.
    # Errexit is lowered only around the pipe so both producer and consumer statuses remain legible.
    # Capture the ENTIRE PIPESTATUS array immediately: any later assignment resets PIPESTATUS.
    set +e
    gunzip -c "$dump_path" | psql "$dsn" -v ON_ERROR_STOP=1 >"$restore_log" 2>&1
    pipe_statuses=("${PIPESTATUS[@]}")
    gunzip_rc=${pipe_statuses[0]}
    restore_rc=${pipe_statuses[1]}
    set -e

    # Judge psql first: when it aborts, gunzip commonly receives consequential SIGPIPE (141).
    if [ "$restore_rc" -ne 0 ]; then
        echo "Restore aborted with psql rc=$restore_rc; private restore log was not printed" >&2
        exit 3
    fi
    if [ "$gunzip_rc" -eq 141 ]; then
        echo "Warning: gunzip received SIGPIPE after successful psql restore" >&2
    elif [ "$gunzip_rc" -ne 0 ]; then
        echo "Archive decompression failed with rc=$gunzip_rc" >&2
        exit 4
    fi

    set +e
    python3 "$REPO_ROOT/scripts/ci/restore_drill_verify.py" --dsn "$dsn" --json \
        >"$WORK_DIR/verify.json" 2>"$WORK_DIR/verify.err"
    verify_rc=$?
    set -e
    aggregate=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["aggregate"])' \
        "$WORK_DIR/verify.json" 2>/dev/null || echo CANNOT-VERIFY)

    echo "Restore drill verdict=$aggregate backup=$latest bytes=$dump_bytes"
    case "$verify_rc" in
        0) return 0 ;;
        1) exit 5 ;;
        3) exit 2 ;;
        *) exit 2 ;;
    esac
}

# Mini has no `timeout`; run the payload in its own process group and let a pure-bash
# watchdog terminate that group after 30 minutes. The parent cleanup trap removes the container.
set -m
drill_main &
DRILL_PID=$!
(
    sleep "$TIMEOUT_SECONDS"
    if kill -0 "$DRILL_PID" 2>/dev/null; then
        : > "$WORK_DIR/watchdog-fired"
        kill -TERM "-$DRILL_PID" 2>/dev/null || kill -TERM "$DRILL_PID" 2>/dev/null || true
        sleep 5
        kill -KILL "-$DRILL_PID" 2>/dev/null || kill -KILL "$DRILL_PID" 2>/dev/null || true
    fi
) &
WATCHDOG_PID=$!

set +e
wait "$DRILL_PID"
DRILL_RC=$?
set -e
kill "$WATCHDOG_PID" 2>/dev/null || true
wait "$WATCHDOG_PID" 2>/dev/null || true
WATCHDOG_PID=""
set +m

if [ -f "$WORK_DIR/watchdog-fired" ]; then
    echo "CANNOT-VERIFY: restore drill exceeded the 30-minute cap" >&2
    exit 124
fi
exit "$DRILL_RC"
