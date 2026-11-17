#!/usr/bin/env bash
# NovaShop LAB-11 -- Elasticsearch index templates and daily index bootstrap.
# Usage: bash scripts/setup-elasticsearch-indices.sh [host:port] [--reset-today]
set -euo pipefail

ES_HOST="${1:-localhost:9200}"
RESET_TODAY="${2:-}"
BASE_URL="http://${ES_HOST}"
TODAY="$(date -u +%Y.%m.%d)"

if [[ "$RESET_TODAY" != "" && "$RESET_TODAY" != "--reset-today" ]]; then
  printf 'Usage: %s [host:port] [--reset-today]\n' "$0" >&2
  exit 2
fi

curl -fsS --connect-timeout 5 "${BASE_URL}/_cluster/health" >/dev/null

template_body='{
  "index_patterns": ["novashop-docker-*", "novashop-k8s-*", "novashop-jenkins-*", "novashop-ubuntu-*"],
  "priority": 200,
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "dynamic": true,
      "properties": {
        "@timestamp": { "type": "date" },
        "message": { "type": "text", "fields": { "keyword": { "type": "keyword", "ignore_above": 1024 } } },
        "log_source": { "type": "keyword" },
        "service": { "type": "keyword" },
        "level": { "type": "keyword" },
        "trace_id": { "type": "keyword" },
        "span_id": { "type": "keyword" },
        "http_status": { "type": "integer" }
      }
    }
  }
}'

curl -fsS -X PUT "${BASE_URL}/_index_template/novashop-lab-logs-v1" \
  -H 'Content-Type: application/json' \
  -d "$template_body" >/dev/null

indices=(
  "novashop-docker-${TODAY}"
  "novashop-k8s-${TODAY}"
  "novashop-jenkins-${TODAY}"
  "novashop-ubuntu-${TODAY}"
)

if [[ "$RESET_TODAY" == "--reset-today" ]]; then
  for index in "${indices[@]}"; do
    curl -fsS -X DELETE "${BASE_URL}/${index}" >/dev/null 2>&1 || true
  done
fi

for index in "${indices[@]}"; do
  curl -fsS -X PUT "${BASE_URL}/${index}" >/dev/null 2>&1 || true
  # Fluent Bit can create an index seconds before this bootstrap script runs.
  # Apply the single-node setting to both newly-created and pre-existing daily
  # indices so the cluster does not remain yellow because of an unassignable
  # replica shard.
  curl -fsS -X PUT "${BASE_URL}/${index}/_settings" \
    -H 'Content-Type: application/json' \
    -d '{"index":{"number_of_replicas":0}}' >/dev/null
done

printf 'NovaShop LAB-11 index template and daily indices are ready (%s).\n' "$TODAY"
curl -fsS "${BASE_URL}/_cat/indices/novashop-*?v"
