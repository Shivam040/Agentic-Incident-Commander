#!/usr/bin/env bash
set -euo pipefail

# Git Bash/MSYS on Windows automatically converts Linux-looking paths
# such as /tmp before invoking docker.exe. Disable that conversion so
# container paths remain valid Linux paths.
if [[ -n "${MSYSTEM:-}" ]]; then
  export MSYS_NO_PATHCONV=1
  export MSYS2_ARG_CONV_EXCL='*'
fi

CONTAINER="incident-commander-ci"
IMAGE="agentic-incident-commander:ci"
LOG_FILE="docker-smoke.log"

cleanup() {
  docker logs "$CONTAINER" > "$LOG_FILE" 2>&1 || true
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting hardened deterministic container..."

docker run -d \
  --name "$CONTAINER" \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  -e AI_MODE=deterministic \
  -e RUNBOOK_RETRIEVAL=lexical \
  -e LANGSMITH_TRACING=false \
  -e RUN_LLM_TESTS=0 \
  -e INCIDENT_COMMANDER_DATA_DIR=/app/data \
  -e CHECKPOINT_DB_PATH=/tmp/incident_commander.sqlite \
  -e RUNBOOK_VECTOR_INDEX_PATH=/tmp/runbooks.json \
  -p 8000:8000 \
  "$IMAGE"

echo "Waiting for /health..."

HEALTH_JSON=""

for attempt in $(seq 1 30); do
  if HEALTH_JSON=$(curl --fail --silent http://127.0.0.1:8000/health); then
    break
  fi

  if [ "$attempt" -eq 30 ]; then
    echo "Container did not become healthy in time."
    docker logs "$CONTAINER"
    exit 1
  fi

  sleep 2
done

printf '%s' "$HEALTH_JSON" | python -c "
import json
import sys

health = json.load(sys.stdin)

assert health['status'] == 'ok', health
assert health['checkpoint_backend'] == 'sqlite', health
assert health['observability']['prometheus_metrics'] is True, health

print('health endpoint: PASS')
"

curl --fail --silent http://127.0.0.1:8000/metrics \
  | grep -q "incident_commander_http_requests_total"

echo "prometheus endpoint: PASS"

echo "Testing deterministic incident API workflow..."

INCIDENT_JSON=$(
  curl --fail --silent \
    -H 'Content-Type: application/json' \
    -d '{"service":"recommendation-api","symptom":"high latency and elevated 503 errors"}' \
    http://127.0.0.1:8000/incidents
)

printf '%s' "$INCIDENT_JSON" | python -c "
import json
import sys

payload = json.load(sys.stdin)

assert payload.get('thread_id'), payload
assert 'state' in payload, payload

print('incident API workflow: PASS')
"

UID_IN_CONTAINER=$(docker exec "$CONTAINER" id -u)

if [ "$UID_IN_CONTAINER" = "0" ]; then
  echo "Container unexpectedly runs as root."
  exit 1
fi

echo "non-root runtime: PASS (uid=$UID_IN_CONTAINER)"

READ_ONLY=$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$CONTAINER")

if [ "$READ_ONLY" != "true" ]; then
  echo "Root filesystem is not read-only."
  exit 1
fi

echo "read-only root filesystem: PASS"

CAP_DROP=$(docker inspect -f '{{json .HostConfig.CapDrop}}' "$CONTAINER")

echo "$CAP_DROP" | grep -qi 'ALL'

echo "capabilities dropped: PASS"

SECURITY_OPT=$(docker inspect -f '{{json .HostConfig.SecurityOpt}}' "$CONTAINER")

echo "$SECURITY_OPT" | grep -q 'no-new-privileges'

echo "no-new-privileges: PASS"

echo "Stage 4D Docker CI smoke: PASS"