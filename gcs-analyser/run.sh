#!/usr/bin/env bash
# Convenience wrapper for the GCS Analyser.
#   ./run.sh                       → scan ALL buckets in the default project, make PDF
#   ./run.sh -p my-proj -b a,b     → specific project + buckets
#   ./run.sh --csv                 → also dump full per-object CSV
# Any flags are passed straight through to gcs_analyser.py.
set -euo pipefail
cd "$(dirname "$0")"

# Verify Application Default Credentials exist; hint if not.
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "⚠️  No Application Default Credentials found."
  echo "   Run:  gcloud auth application-default login"
  echo "   (then re-run this script)"
  exit 1
fi

exec python3 gcs_analyser.py "$@"
