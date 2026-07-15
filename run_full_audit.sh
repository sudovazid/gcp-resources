#!/bin/bash

# Define colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ID="${GCP_PROJECT_ID:?Error: GCP_PROJECT_ID env var not set. Usage: GCP_PROJECT_ID=my-project ./run_full_audit.sh}"
# Export format: "csv", "xlsx-only", "pdf-only", or "all" (default: all)
# Override with: EXPORT_FORMATS="xlsx-only" ./run_full_audit.sh
EXPORT_FORMATS="${EXPORT_FORMATS:-all}"
OUTPUT_DIR="output"

echo -e "${BLUE}====================================================${NC}"
echo -e "${CYAN}   🌩️  NON-INTERACTIVE GCP RESOURCE AUDIT 🌩️       ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "Target Project ID: ${GREEN}$PROJECT_ID${NC}"
echo -e "Export Formats:    ${GREEN}$EXPORT_FORMATS${NC}"
echo -e "                   (csv | xlsx-only | pdf-only | all)"
echo -e "Output Directory:  ${GREEN}./$OUTPUT_DIR/${NC}"
echo -e "${BLUE}====================================================${NC}"

# Setup output directory
mkdir -p "$OUTPUT_DIR"

# Clean up any leftover CSV files in root directory to avoid pollution
rm -f *.csv *.xlsx *.pdf

finalize_report() {
    local report_name="$1"
    local found=false
    for csv_file in *.csv; do
        if [ -f "$csv_file" ]; then
            found=true
            # Skip converter for CSV-only mode
            if [ "$EXPORT_FORMATS" != "csv" ]; then
                echo -e "Converting reports for: ${YELLOW}$csv_file${NC}"
                python3 utils/export_converter.py "$csv_file" "$EXPORT_FORMATS"
            fi
            # For xlsx-only or pdf-only, remove the intermediate CSV
            if [ "$EXPORT_FORMATS" = "xlsx-only" ] || [ "$EXPORT_FORMATS" = "pdf-only" ]; then
                rm -f "$csv_file"
            fi
            # Move generated reports to the output folder
            local base_name="${csv_file%.csv}"
            mv "$base_name"* "$OUTPUT_DIR"/ 2>/dev/null
        fi
    done
    if [ "$found" = true ]; then
        echo -e "${GREEN}📂 ${report_name} Reports saved in './$OUTPUT_DIR/'${NC}"
    else
        echo -e "${RED}⚠️  No reports generated for ${report_name}.${NC}"
    fi
}

run_audit() {
    local service_name="$1"
    local python_script="$2"
    
    echo -e "\n${BLUE}Executing ${service_name} Resource Audit...${NC}"
    if [ -f "$python_script" ]; then
        python3 "$python_script" "$PROJECT_ID"
        finalize_report "$service_name"
    else
        echo -e "${RED}❌ Script not found: $python_script${NC}"
    fi
}

# Run audits for all services
run_audit "GCS" "gcs/gcs_resource.py"
run_audit "Cloud Run" "cloud_run/cloud_resource.py"
run_audit "Cloud SQL" "cloud_sql/cloud_sql_resource.py"
run_audit "Redis" "redis/redis_resource.py"
run_audit "Artifact Registry" "artifact_registry/ar_resource.py"
run_audit "Compute Engine & Networking" "compute_engine/gce_resource.py"
run_audit "Dialogflow CX Agent" "agent-platform/agent_resource.py"
run_audit "Pub/Sub" "pubsub/pubsub_resource.py"
run_audit "BigQuery" "bigquery/bq_resource.py"
run_audit "IAM & Service Accounts" "iam/iam_resource.py"
run_audit "GKE" "gke/gke_resource.py"
run_audit "Secret Manager" "secret_manager/sm_resource.py"
run_audit "Cloud Functions" "cloud_functions/gcf_resource.py"
run_audit "App Engine" "app_engine/gae_resource.py"
run_audit "Cloud Logging" "cloud_logging/logging_resource.py"
run_audit "Cloud CDN" "cloud_cdn/cdn_resource.py"
run_audit "Cloud Scheduler" "cloud_scheduler/scheduler_resource.py"
run_audit "Cloud KMS" "kms/kms_resource.py"
run_audit "VPC Service Controls" "vpc_sc/vpc_sc_resource.py"
run_audit "Cloud Composer" "composer/composer_resource.py"
run_audit "Vertex AI" "vertex_ai/vertex_resource.py"
run_audit "Enabled APIs & Services" "service_usage/su_resource.py"
run_audit "Firestore" "firestore/firestore_resource.py"
run_audit "Cloud Spanner" "cloud_spanner/spanner_resource.py"
run_audit "AlloyDB" "alloydb/alloydb_resource.py"
run_audit "Cloud DNS" "cloud_dns/dns_resource.py"
run_audit "Cloud Tasks" "cloud_tasks/tasks_resource.py"
run_audit "Eventarc" "eventarc/eventarc_resource.py"
run_audit "Cloud Build" "cloud_build/cloudbuild_resource.py"
run_audit "Cloud Load Balancing" "cloud_load_balancing/lb_resource.py"
run_audit "Cloud NAT" "cloud_nat/nat_resource.py"
run_audit "Dataflow" "dataflow/dataflow_resource.py"
run_audit "Dataproc" "dataproc/dataproc_resource.py"
run_audit "Binary Authorization" "binary_authorization/binauthz_resource.py"
run_audit "Data Catalog" "data_catalog/datacatalog_resource.py"

echo -e "\n${GREEN}⚡⚡⚡ Full GCP Resource Audit completed successfully! ⚡⚡⚡${NC}"
