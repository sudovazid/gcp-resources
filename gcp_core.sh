#!/bin/bash

# Define colors for beautiful terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Config file for persisting preferences
CONFIG_DIR="${HOME}/.config/gcp-auditor"
CONFIG_FILE="${CONFIG_DIR}/config"
LAST_PROJECT=""
LAST_FORMAT="4"

load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        while IFS='=' read -r key value; do
            case "$key" in
                LAST_PROJECT) LAST_PROJECT="$value" ;;
                LAST_FORMAT) LAST_FORMAT="$value" ;;
            esac
        done < "$CONFIG_FILE"
    fi
}

save_config() {
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_FILE" <<-EOF
LAST_PROJECT=${PROJECT_ID:-}
LAST_FORMAT=${EXPORT_CHOICE:-$LAST_FORMAT}
EOF
}

# 1. Welcome Message
echo -e "${BLUE}====================================================${NC}"
echo -e "${CYAN}      🌩️  GCP RESOURCE CHECK & AUDIT TOOL 🌩️       ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "Welcome! This tool will help you analyze your Google Cloud resources."
echo -e "Type ${YELLOW}h${NC} in any menu for details on available services."
echo ""

load_config

# 2. Check GCP CLI Setup
echo -e "${YELLOW}[System Check] Verifying Google Cloud CLI setup...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: 'gcloud' CLI is not installed or not in your PATH.${NC}"
    echo "Please install the Google Cloud SDK from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo -e "${GREEN}✅ gcloud CLI is installed.${NC}"

# 3. Check and Install Python Dependencies
echo -e "${YELLOW}[System Check] Verifying Python dependencies...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: 'python3' is not installed. Please install Python 3.${NC}"
    exit 1
fi

# Fast Check: Check if dependencies are already importable
DEPENDENCIES_OK=true
python3 -c "
import google.cloud.storage
import googleapiclient
import google.cloud.compute
import google.cloud.pubsub
import google.cloud.bigquery
import google.cloud.container
import google.cloud.secretmanager
import google.cloud.functions
import google.cloud.dialogflowcx_v3
import openpyxl
import fpdf
import reportlab
" &>/dev/null || DEPENDENCIES_OK=false

if [ "$DEPENDENCIES_OK" = true ]; then
    echo -e "${GREEN}✅ Python dependencies are already satisfied.${NC}"
else
    if ! python3 -m pip --version &> /dev/null; then
        echo -e "${RED}❌ Error: 'pip' is not installed for python3. Please install pip.${NC}"
        exit 1
    fi

    echo -e "${CYAN}Installing/Updating required Python libraries (this might take a few seconds)...${NC}"
    # Use --break-system-packages to bypass macOS Homebrew restrictions
    if python3 -m pip install --user --break-system-packages -q openpyxl fpdf2 reportlab google-cloud-monitoring google-cloud-storage google-cloud-run google-api-python-client google-cloud-redis google-cloud-artifact-registry google-cloud-compute google-cloud-dialogflow-cx google-cloud-pubsub google-cloud-bigquery google-cloud-container google-cloud-secret-manager google-cloud-functions; then
        echo -e "${GREEN}✅ Python dependencies installed successfully.${NC}"
    else
        echo -e "${RED}❌ Error installing Python dependencies. Please check your Python environment.${NC}"
        exit 1
    fi
fi

# 4. Check Authentication Status
echo -e "${YELLOW}[System Check] Verifying Authentication...${NC}"

# Try to check if Python can acquire credentials automatically
AUTH_OK=true
python3 -c "
import google.auth
try:
    google.auth.default()
except Exception:
    exit(1)
" &>/dev/null || AUTH_OK=false

if [ "$AUTH_OK" = false ]; then
    echo -e "${RED}⚠️  No valid Google Cloud Application Default Credentials (ADC) found.${NC}"
    echo -e "Please select an option to authenticate:"
    echo "1) Authenticate via browser (gcloud auth application-default login)"
    echo "2) Provide path to a Service Account Key JSON file"
    echo "3) Skip check (credentials inherited from environment/metadata server)"
    read -p "Enter choice [1-3]: " AUTH_CHOICE
    
    case $AUTH_CHOICE in
        1)
            echo "Launching browser for authentication..."
            gcloud auth application-default login
            ;;
        2)
            read -p "Enter absolute path to your service account key JSON file: " SA_PATH
            if [ -f "$SA_PATH" ]; then
                export GOOGLE_APPLICATION_CREDENTIALS="$SA_PATH"
                echo -e "${GREEN}✅ GOOGLE_APPLICATION_CREDENTIALS set to: $SA_PATH${NC}"
            else
                echo -e "${RED}❌ File not found: $SA_PATH. Skipping auth configuration.${NC}"
            fi
            ;;
        3)
            echo "Skipping authentication check. Relying on default environment credentials."
            ;;
        *)
            echo "Invalid choice. Skipping authentication configuration."
            ;;
    esac
else
    echo -e "${GREEN}✅ Successfully authenticated with Google Cloud.${NC}"
fi

echo ""

# 5. Setup Output Directory
OUTPUT_DIR="output"
mkdir -p "$OUTPUT_DIR"
echo -e "${YELLOW}[System Check] Output directory set to './$OUTPUT_DIR/'${NC}"
echo ""

# 6. Get Project ID (Interactive Selection)
echo -e "${YELLOW}[Configuration] Setting up GCP Account & Project...${NC}"

# Get active account
ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
echo -e "Currently active account: ${GREEN}${ACTIVE_ACCOUNT:-None}${NC}"

# List all authenticated accounts (compatible with Bash 3.2+)
ACCOUNTS=()
while IFS= read -r line; do
    [ -n "$line" ] && ACCOUNTS+=("$line")
done < <(gcloud auth list --format="value(account)" 2>/dev/null)

if [ ${#ACCOUNTS[@]} -eq 0 ]; then
    echo -e "${RED}⚠️  No authenticated accounts found.${NC}"
    echo "Please authenticate now:"
    gcloud auth login
    gcloud auth application-default login
    ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
else
    echo -e "\nAvailable authenticated accounts:"
    for i in "${!ACCOUNTS[@]}"; do
        if [ "${ACCOUNTS[$i]}" = "$ACTIVE_ACCOUNT" ]; then
            echo -e "  $((i+1))) ${ACCOUNTS[$i]} ${CYAN}(Active)${NC}"
        else
            echo -e "  $((i+1))) ${ACCOUNTS[$i]}"
        fi
    done
    echo -e "  $(( ${#ACCOUNTS[@]} + 1 ))) Log in to a new account"
    echo -e "  $(( ${#ACCOUNTS[@]} + 2 ))) Keep active account & proceed"

    read -p "👉 Select account option [1-$(( ${#ACCOUNTS[@]} + 2 ))]: " ACCT_CHOICE
    
    if [[ "$ACCT_CHOICE" =~ ^[0-9]+$ ]]; then
        if [ "$ACCT_CHOICE" -le "${#ACCOUNTS[@]}" ]; then
            SELECTED_ACCOUNT="${ACCOUNTS[$((ACCT_CHOICE-1))]}"
            echo -e "Switching to account: ${GREEN}$SELECTED_ACCOUNT${NC}"
            gcloud config set account "$SELECTED_ACCOUNT" >/dev/null 2>&1
            ACTIVE_ACCOUNT="$SELECTED_ACCOUNT"
        elif [ "$ACCT_CHOICE" -eq "$(( ${#ACCOUNTS[@]} + 1 ))" ]; then
            echo "Logging in to new account..."
            gcloud auth login
            gcloud auth application-default login
            ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
        fi
    fi
fi

# Project Selection
echo -e "\n${YELLOW}[Configuration] Fetching available projects for $ACTIVE_ACCOUNT...${NC}"

# Get active project (default fallback)
DEFAULT_PROJECT=$(gcloud config get-value project 2>/dev/null)

# List projects (compatible with Bash 3.2+)
PROJECTS=()
while IFS= read -r line; do
    [ -n "$line" ] && PROJECTS+=("$line")
done < <(gcloud projects list --format="value(projectId, name)" 2>/dev/null)

if [ ${#PROJECTS[@]} -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No projects found or unable to list projects.${NC}"
    read -p "👉 Enter your GCP Project ID manually: " PROJECT_ID
else
    echo -e "Available GCP Projects:"
    for i in "${!PROJECTS[@]}"; do
        PROJ_ID=$(echo "${PROJECTS[$i]}" | awk '{print $1}')
        PROJ_NAME=$(echo "${PROJECTS[$i]}" | awk '{$1=""; print $0}' | sed 's/^[ \t]*//')
        
        if [ "$PROJ_ID" = "$DEFAULT_PROJECT" ]; then
            echo -e "  $((i+1))) ${PROJ_ID} - ${CYAN}${PROJ_NAME}${NC} ${GREEN}(Active Default)${NC}"
        else
            echo -e "  $((i+1))) ${PROJ_ID} - ${CYAN}${PROJ_NAME}${NC}"
        fi
    done
    echo -e "  $(( ${#PROJECTS[@]} + 1 ))) Enter a Project ID manually"
    
    read -p "👉 Select project option [1-$(( ${#PROJECTS[@]} + 1 ))]: " PROJ_CHOICE
    
    if [[ "$PROJ_CHOICE" =~ ^[0-9]+$ ]] && [ "$PROJ_CHOICE" -le "${#PROJECTS[@]}" ]; then
        PROJECT_ID=$(echo "${PROJECTS[$((PROJ_CHOICE-1))]}" | awk '{print $1}')
    else
        read -p "👉 Enter your GCP Project ID manually: " PROJECT_ID
    fi
fi

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Project ID cannot be empty. Exiting.${NC}"
    exit 1
fi

# Set the active project in gcloud configuration
echo -e "Setting active GCP project to: ${GREEN}$PROJECT_ID${NC}"
gcloud config set project "$PROJECT_ID" >/dev/null 2>&1
save_config

# 7. Select Export Formats
echo -e "\n👉 Select report export formats:"
echo "1) CSV only"
echo "2) Excel (.xlsx) only"
echo "3) PDF only"
echo "4) All formats (CSV, Excel, PDF)"
read -p "Choose choice [1-4, default ${LAST_FORMAT:-4}]: " EXPORT_CHOICE
if [ -z "$EXPORT_CHOICE" ]; then
    EXPORT_CHOICE="${LAST_FORMAT:-4}"
fi
case $EXPORT_CHOICE in
    1) EXPORT_FORMATS="csv" ;;
    2) EXPORT_FORMATS="xlsx-only" ;;
    3) EXPORT_FORMATS="pdf-only" ;;
    4|*) EXPORT_FORMATS="all" ;;
esac

# Show export format preview
case $EXPORT_FORMATS in
    "csv") FMT_LABEL="CSV"; EXT=".csv" ;;
    "xlsx-only") FMT_LABEL="Excel"; EXT=".xlsx" ;;
    "pdf-only") FMT_LABEL="PDF"; EXT=".pdf" ;;
    "all") FMT_LABEL="CSV + Excel + PDF"; EXT="(.csv, .xlsx, .pdf)" ;;
esac
save_config
echo -e "Reports will be generated as: ${GREEN}${FMT_LABEL}${NC}"
echo -e "Example output: ${CYAN}${PROJECT_ID}_<service>_audit${EXT}${NC}"

# Track per-service resource counts for final summary
AUDIT_RESULTS=()

detect_api_error() {
    local service="$1"
    local logfile="$2"
    if [ -f "$logfile" ] && grep -qiE "(is not enabled|access denied|forbidden|permission denied|not found)" "$logfile" 2>/dev/null; then
        local api_name
        case "$service" in
            "Firestore") api_name="firestore.googleapis.com" ;;
            "Cloud Spanner") api_name="spanner.googleapis.com" ;;
            "AlloyDB") api_name="alloydb.googleapis.com" ;;
            "Cloud DNS") api_name="dns.googleapis.com" ;;
            "Cloud Tasks") api_name="cloudtasks.googleapis.com" ;;
            "Eventarc") api_name="eventarc.googleapis.com" ;;
            "Cloud Build") api_name="cloudbuild.googleapis.com" ;;
            "Cloud Load Balancing") api_name="compute.googleapis.com" ;;
            "Cloud NAT") api_name="compute.googleapis.com" ;;
            "Dataflow") api_name="dataflow.googleapis.com" ;;
            "Dataproc") api_name="dataproc.googleapis.com" ;;
            "Binary Authorization") api_name="binaryauthorization.googleapis.com" ;;
            "Data Catalog") api_name="datacatalog.googleapis.com" ;;
            "GCS") api_name="storage.googleapis.com" ;;
            "Cloud Run") api_name="run.googleapis.com" ;;
            "Cloud SQL") api_name="sqladmin.googleapis.com" ;;
            "Redis") api_name="redis.googleapis.com" ;;
            "Artifact Registry") api_name="artifactregistry.googleapis.com" ;;
            "Compute Engine") api_name="compute.googleapis.com" ;;
            "Dialogflow") api_name="dialogflow.googleapis.com" ;;
            "Pub/Sub") api_name="pubsub.googleapis.com" ;;
            "BigQuery") api_name="bigquery.googleapis.com" ;;
            "IAM") api_name="iam.googleapis.com" ;;
            "GKE") api_name="container.googleapis.com" ;;
            "Secret Manager") api_name="secretmanager.googleapis.com" ;;
            "Cloud Functions") api_name="cloudfunctions.googleapis.com" ;;
            "App Engine") api_name="appengine.googleapis.com" ;;
            "Cloud Logging") api_name="logging.googleapis.com" ;;
            "Cloud CDN") api_name="cdn.googleapis.com" ;;
            "Cloud Scheduler") api_name="cloudscheduler.googleapis.com" ;;
            "Cloud KMS") api_name="cloudkms.googleapis.com" ;;
            "VPC SC") api_name="accesscontextmanager.googleapis.com" ;;
            "Cloud Composer") api_name="composer.googleapis.com" ;;
            "Vertex AI") api_name="aiplatform.googleapis.com" ;;
            *) api_name="" ;;
        esac
        if [ -n "$api_name" ]; then
            echo -e "  ${YELLOW}💡 Enable with: gcloud services enable ${api_name}${NC}"
        fi
    fi
}

finalize_report() {
    local report_name="$1"
    local found=false
    local tmp_log
    tmp_log=$(mktemp)
    for csv_file in *.csv; do
        if [ -f "$csv_file" ]; then
            found=true
            # Convert formats if needed
            if [ "$EXPORT_FORMATS" != "csv" ]; then
                python3 utils/export_converter.py "$csv_file" "$EXPORT_FORMATS" 2>"$tmp_log"
                detect_api_error "$report_name" "$tmp_log"
            fi
            # For xlsx-only or pdf-only, remove the intermediate CSV
            if [ "$EXPORT_FORMATS" = "xlsx-only" ] || [ "$EXPORT_FORMATS" = "pdf-only" ]; then
                rm -f "$csv_file"
            fi
            # Move all generated files for this CSV to output directory
            local base_name="${csv_file%.csv}"
            mv "$base_name"* "$OUTPUT_DIR"/ 2>/dev/null
        fi
    done
    rm -f "$tmp_log"
    if [ "$found" = true ]; then
        echo -e "${GREEN}📂 ${report_name} Reports saved in './$OUTPUT_DIR/'${NC}"
        AUDIT_RESULTS+=("${GREEN}✓${NC} ${report_name}")
    else
        echo -e "${YELLOW}⚠️ No report files were generated for ${report_name}.${NC}"
        AUDIT_RESULTS+=("${RED}✗${NC} ${report_name}")
    fi
}

run_audit_gcs() {
    echo -e "\n${BLUE}Executing GCS Resource Audit...${NC}"
    python3 gcs/gcs_resource.py "$PROJECT_ID"
    finalize_report "GCS"
}
run_gcs_analyser() {
    # Deep GCS analysis → polished PDF (size · folders · lifecycle · versioning · cost).
    # Self-contained: generates its own PDF/CSV (does NOT use finalize_report).
    echo -e "\n${BLUE}Executing GCS Analyser (size · lifecycle · versioning · cost → PDF)...${NC}"
    echo -e "${YELLOW}⚠️  Scans every object; a full all-buckets scan on large projects can be slow${NC}"
    echo -e "${YELLOW}    and incurs Class A/B list operations. Tip: target a bucket to start.${NC}"
    read -p "👉 Bucket name(s) (comma-separated), or press ENTER to scan ALL buckets: " GCS_AN_BUCKETS
    read -p "👉 Folder depth — path segments that define a 'folder' [default 1]: " GCS_AN_DEPTH
    read -p "👉 Largest N files to list per bucket in the PDF [default 15]: " GCS_AN_TOP

    # Validate numeric inputs; fall back to defaults if blank or non-numeric.
    if ! [[ "$GCS_AN_DEPTH" =~ ^[0-9]+$ ]]; then GCS_AN_DEPTH=1; fi
    if ! [[ "$GCS_AN_TOP"   =~ ^[0-9]+$ ]]; then GCS_AN_TOP=15; fi

    local ts out args
    ts=$(date -u +%Y%m%d_%H%M%S)
    out="$OUTPUT_DIR/gcs_analysis_${PROJECT_ID}_${ts}.pdf"
    args=(--project "$PROJECT_ID" --output "$out" --csv
          --prefix-depth "$GCS_AN_DEPTH" --top-files "$GCS_AN_TOP")
    if [ -n "$GCS_AN_BUCKETS" ]; then
        args+=(--buckets "$GCS_AN_BUCKETS")
    fi
    echo -e "${CYAN}→ depth=${GCS_AN_DEPTH} · top-files=${GCS_AN_TOP} · buckets=${GCS_AN_BUCKETS:-ALL}${NC}"

    if python3 gcs-analyser/gcs_analyser.py "${args[@]}"; then
        echo -e "${GREEN}📂 GCS Analyser report (PDF + CSV) saved in './$OUTPUT_DIR/'${NC}"
    else
        echo -e "${RED}❌ GCS Analyser failed. Check auth (ADC) and bucket permissions.${NC}"
    fi
}
run_audit_run() {
    echo -e "\n${BLUE}Executing Cloud Run Resource Audit...${NC}"
    python3 cloud_run/cloud_resource.py "$PROJECT_ID"
    finalize_report "Cloud Run"
}
run_audit_sql() {
    echo -e "\n${BLUE}Executing Cloud SQL Resource Audit...${NC}"
    mkdir -p cloud_sql
    python3 cloud_sql/cloud_sql_resource.py "$PROJECT_ID"
    finalize_report "Cloud SQL"
}
run_audit_redis() {
    echo -e "\n${BLUE}Executing Cloud Memorystore (Redis) Audit...${NC}"
    python3 redis/redis_resource.py "$PROJECT_ID"
    finalize_report "Redis"
}
run_audit_ar() {
    echo -e "\n${BLUE}Executing Artifact Registry Audit...${NC}"
    python3 artifact_registry/ar_resource.py "$PROJECT_ID"
    finalize_report "Artifact Registry"
}
run_audit_gce() {
    echo -e "\n${BLUE}Executing Compute Engine & Networking Audit...${NC}"
    python3 compute_engine/gce_resource.py "$PROJECT_ID"
    finalize_report "Compute Engine & Networking"
}
run_audit_agent() {
    echo -e "\n${BLUE}Executing Dialogflow CX Agent Audit...${NC}"
    python3 agent-platform/agent_resource.py "$PROJECT_ID"
    finalize_report "Dialogflow CX Agent"
}
run_audit_pubsub() {
    echo -e "\n${BLUE}Executing Pub/Sub Resource Audit...${NC}"
    python3 pubsub/pubsub_resource.py "$PROJECT_ID"
    finalize_report "Pub/Sub"
}
run_audit_bq() {
    echo -e "\n${BLUE}Executing BigQuery Resource Audit...${NC}"
    python3 bigquery/bq_resource.py "$PROJECT_ID"
    finalize_report "BigQuery"
}
run_audit_iam() {
    echo -e "\n${BLUE}Executing IAM & Service Accounts Audit...${NC}"
    python3 iam/iam_resource.py "$PROJECT_ID"
    finalize_report "IAM & Service Accounts"
}
run_audit_gke() {
    echo -e "\n${BLUE}Executing GKE Resource Audit...${NC}"
    python3 gke/gke_resource.py "$PROJECT_ID"
    finalize_report "GKE"
}
run_audit_sm() {
    echo -e "\n${BLUE}Executing Secret Manager Resource Audit...${NC}"
    python3 secret_manager/sm_resource.py "$PROJECT_ID"
    finalize_report "Secret Manager"
}
run_audit_gcf() {
    echo -e "\n${BLUE}Executing Cloud Functions Resource Audit...${NC}"
    python3 cloud_functions/gcf_resource.py "$PROJECT_ID"
    finalize_report "Cloud Functions"
}
run_audit_gae() {
    echo -e "\n${BLUE}Executing App Engine Resource Audit...${NC}"
    python3 app_engine/gae_resource.py "$PROJECT_ID"
    finalize_report "App Engine"
}
run_audit_logging() {
    echo -e "\n${BLUE}Executing Cloud Logging Resource Audit...${NC}"
    python3 cloud_logging/logging_resource.py "$PROJECT_ID"
    finalize_report "Cloud Logging"
}
run_audit_cdn() {
    echo -e "\n${BLUE}Executing Cloud CDN Resource Audit...${NC}"
    python3 cloud_cdn/cdn_resource.py "$PROJECT_ID"
    finalize_report "Cloud CDN"
}
run_audit_scheduler() {
    echo -e "\n${BLUE}Executing Cloud Scheduler Resource Audit...${NC}"
    python3 cloud_scheduler/scheduler_resource.py "$PROJECT_ID"
    finalize_report "Cloud Scheduler"
}
run_audit_kms() {
    echo -e "\n${BLUE}Executing Cloud KMS Resource Audit...${NC}"
    python3 kms/kms_resource.py "$PROJECT_ID"
    finalize_report "Cloud KMS"
}
run_audit_vpc_sc() {
    echo -e "\n${BLUE}Executing VPC Service Controls Resource Audit...${NC}"
    python3 vpc_sc/vpc_sc_resource.py "$PROJECT_ID"
    finalize_report "VPC Service Controls"
}
run_audit_composer() {
    echo -e "\n${BLUE}Executing Cloud Composer Resource Audit...${NC}"
    python3 composer/composer_resource.py "$PROJECT_ID"
    finalize_report "Cloud Composer"
}
run_audit_vertex() {
    echo -e "\n${BLUE}Executing Vertex AI Resource Audit...${NC}"
    python3 vertex_ai/vertex_resource.py "$PROJECT_ID"
    finalize_report "Vertex AI"
}
run_audit_su() {
    echo -e "\n${BLUE}Executing Enabled APIs & Services Audit...${NC}"
    python3 service_usage/su_resource.py "$PROJECT_ID"
    finalize_report "Enabled APIs & Services"
}
run_audit_firestore() {
    echo -e "\n${BLUE}Executing Firestore Audit...${NC}"
    python3 firestore/firestore_resource.py "$PROJECT_ID"
    finalize_report "Firestore"
}
run_audit_spanner() {
    echo -e "\n${BLUE}Executing Cloud Spanner Audit...${NC}"
    python3 cloud_spanner/spanner_resource.py "$PROJECT_ID"
    finalize_report "Cloud Spanner"
}
run_audit_alloydb() {
    echo -e "\n${BLUE}Executing AlloyDB Audit...${NC}"
    python3 alloydb/alloydb_resource.py "$PROJECT_ID"
    finalize_report "AlloyDB"
}
run_audit_dns() {
    echo -e "\n${BLUE}Executing Cloud DNS Audit...${NC}"
    python3 cloud_dns/dns_resource.py "$PROJECT_ID"
    finalize_report "Cloud DNS"
}
run_audit_tasks() {
    echo -e "\n${BLUE}Executing Cloud Tasks Audit...${NC}"
    python3 cloud_tasks/tasks_resource.py "$PROJECT_ID"
    finalize_report "Cloud Tasks"
}
run_audit_eventarc() {
    echo -e "\n${BLUE}Executing Eventarc Audit...${NC}"
    python3 eventarc/eventarc_resource.py "$PROJECT_ID"
    finalize_report "Eventarc"
}
run_audit_cloudbuild() {
    echo -e "\n${BLUE}Executing Cloud Build Audit...${NC}"
    python3 cloud_build/cloudbuild_resource.py "$PROJECT_ID"
    finalize_report "Cloud Build"
}
run_audit_lb() {
    echo -e "\n${BLUE}Executing Cloud Load Balancing Audit...${NC}"
    python3 cloud_load_balancing/lb_resource.py "$PROJECT_ID"
    finalize_report "Cloud Load Balancing"
}
run_audit_nat() {
    echo -e "\n${BLUE}Executing Cloud NAT Audit...${NC}"
    python3 cloud_nat/nat_resource.py "$PROJECT_ID"
    finalize_report "Cloud NAT"
}
run_audit_dataflow() {
    echo -e "\n${BLUE}Executing Dataflow Audit...${NC}"
    python3 dataflow/dataflow_resource.py "$PROJECT_ID"
    finalize_report "Dataflow"
}
run_audit_dataproc() {
    echo -e "\n${BLUE}Executing Dataproc Audit...${NC}"
    python3 dataproc/dataproc_resource.py "$PROJECT_ID"
    finalize_report "Dataproc"
}
run_audit_binauthz() {
    echo -e "\n${BLUE}Executing Binary Authorization Audit...${NC}"
    python3 binary_authorization/binauthz_resource.py "$PROJECT_ID"
    finalize_report "Binary Authorization"
}
run_audit_datacatalog() {
    echo -e "\n${BLUE}Executing Data Catalog Audit...${NC}"
    python3 data_catalog/datacatalog_resource.py "$PROJECT_ID"
    finalize_report "Data Catalog"
}

run_audit_all() {
    AUDIT_RESULTS=()
    local total=36 current=0
    local start_time end_time elapsed
    start_time=$(date +%s)
    echo -e "\n${YELLOW}⚡ Starting FULL GCP Resource Audit for project: $PROJECT_ID ⚡${NC}"
    echo -e "${CYAN}   Auditing 36 services...${NC}"
    echo ""

    _run_with_progress() {
        current=$((current + 1))
        echo -e "${BLUE}[${current}/${total}]${NC} $1"
    }

    _run_with_progress "Cloud Storage (GCS)" && run_audit_gcs
    _run_with_progress "Cloud Run" && run_audit_run
    _run_with_progress "Cloud SQL" && run_audit_sql
    _run_with_progress "Cloud Memorystore (Redis)" && run_audit_redis
    _run_with_progress "Artifact Registry" && run_audit_ar
    _run_with_progress "Compute Engine & Networking" && run_audit_gce
    _run_with_progress "Dialogflow CX Agent" && run_audit_agent
    _run_with_progress "Pub/Sub" && run_audit_pubsub
    _run_with_progress "BigQuery" && run_audit_bq
    _run_with_progress "IAM & Service Accounts" && run_audit_iam
    _run_with_progress "GKE" && run_audit_gke
    _run_with_progress "Secret Manager" && run_audit_sm
    _run_with_progress "Cloud Functions" && run_audit_gcf
    _run_with_progress "App Engine" && run_audit_gae
    _run_with_progress "Cloud Logging" && run_audit_logging
    _run_with_progress "Cloud CDN" && run_audit_cdn
    _run_with_progress "Cloud Scheduler" && run_audit_scheduler
    _run_with_progress "Cloud KMS" && run_audit_kms
    _run_with_progress "VPC Service Controls" && run_audit_vpc_sc
    _run_with_progress "Cloud Composer" && run_audit_composer
    _run_with_progress "Vertex AI" && run_audit_vertex
    _run_with_progress "Enabled APIs & Services" && run_audit_su
    _run_with_progress "Firestore" && run_audit_firestore
    _run_with_progress "Cloud Spanner" && run_audit_spanner
    _run_with_progress "AlloyDB" && run_audit_alloydb
    _run_with_progress "Cloud DNS" && run_audit_dns
    _run_with_progress "Cloud Tasks" && run_audit_tasks
    _run_with_progress "Eventarc" && run_audit_eventarc
    _run_with_progress "Cloud Build" && run_audit_cloudbuild
    _run_with_progress "Cloud Load Balancing" && run_audit_lb
    _run_with_progress "Cloud NAT" && run_audit_nat
    _run_with_progress "Dataflow" && run_audit_dataflow
    _run_with_progress "Dataproc" && run_audit_dataproc
    _run_with_progress "Binary Authorization" && run_audit_binauthz
    _run_with_progress "Data Catalog" && run_audit_datacatalog

    end_time=$(date +%s)
    elapsed=$((end_time - start_time))
    echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✨ Full GCP Resource Audit Complete ✨${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e " Project:     ${CYAN}${PROJECT_ID}${NC}"
    echo -e " Duration:    ${CYAN}$((elapsed / 60))m $((elapsed % 60))s${NC}"
    echo -e " Output:      ${CYAN}./$OUTPUT_DIR/${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e " ${GREEN}Successful:${NC}"
    for r in "${AUDIT_RESULTS[@]}"; do
        echo -e "   $r"
    done | sort
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
}

show_service_help() {
    local menu="$1"
    echo -e "\n${CYAN}══════════════ SERVICE HELP ══════════════${NC}"
    case "$menu" in
        compute)
            echo -e " ${CYAN}Compute & Kubernetes — what each audit covers:${NC}"
            echo -e "  ${GREEN}1.${NC} Compute Engine   — VMs, disks, snapshots, images, templates, VPCs, health checks"
            echo -e "  ${GREEN}2.${NC} Cloud Run        — Services, revisions, containers, concurrency, traffic, IAM"
            echo -e "  ${GREEN}3.${NC} Cloud Functions  — Functions v1 & v2, triggers, source URLs, runtimes"
            echo -e "  ${GREEN}4.${NC} App Engine       — Applications, services, versions, traffic splits, instances"
            echo -e "  ${GREEN}5.${NC} GKE              — Clusters, node pools, node configs, versions"
            echo -e "  ${GREEN}6.${NC} Cloud Composer   — Environments, Airflow configs, software versions"
            echo -e "  ${GREEN}7.${NC} Cloud LB         — Forwarding rules, backend services, target proxies, URL maps, SSL certs"
            echo -e "  ${GREEN}8.${NC} Cloud NAT        — NAT gateways, router configs, NAT IPs, port allocation"
            echo -e "  ${GREEN}9.${NC} Cloud DNS        — Managed zones, record sets, DNSSEC, visibility"
            ;;
        storage)
            echo -e " ${CYAN}Storage & Database — what each audit covers:${NC}"
            echo -e "  ${GREEN}1.${NC} GCS              — Buckets, sizes (Monitoring), location, class, versioning, encryption"
            echo -e "  ${GREEN}2.${NC} GCS Analyser     — Deep per-object scan: lifecycle, cost, folder breakdown, PDF report"
            echo -e "  ${GREEN}3.${NC} Cloud SQL        — Instances, DB version, tier, disk, backup, IP settings"
            echo -e "  ${GREEN}4.${NC} Redis            — Instances, tier, memory, connectivity"
            echo -e "  ${GREEN}5.${NC} BigQuery         — Datasets, tables, partitions, clustering, routines, recent jobs"
            echo -e "  ${GREEN}6.${NC} Artifact Registry — Repositories, formats (Docker, Maven, npm), locations"
            echo -e "  ${GREEN}7.${NC} Firestore        — Databases, location, concurrency mode, field indexes"
            echo -e "  ${GREEN}8.${NC} Cloud Spanner    — Instances, databases, backups, encryption, version retention"
            echo -e "  ${GREEN}9.${NC} AlloyDB          — Clusters, primary & read instances, backups, continuous backup"
            ;;
        security)
            echo -e " ${CYAN}Identity & Security — what each audit covers:${NC}"
            echo -e "  ${GREEN}1.${NC} IAM              — Policies, custom roles, service accounts, keys"
            echo -e "  ${GREEN}2.${NC} Secret Manager   — Secrets, versions, replication, rotation"
            echo -e "  ${GREEN}3.${NC} Cloud KMS        — Key rings, crypto keys, algorithms, rotation"
            echo -e "  ${GREEN}4.${NC} VPC SC           — Service perimeters, ingress/egress rules, protected services"
            echo -e "  ${GREEN}5.${NC} Binary Auth      — Admission policy, attestors, public keys"
            echo -e "  ${GREEN}6.${NC} Data Catalog     — Tag templates, entry groups, entries, schema"
            ;;
        ops)
            echo -e " ${CYAN}Operations & Integration — what each audit covers:${NC}"
            echo -e "  ${GREEN}1.${NC} Cloud Logging    — Log buckets, sinks, exclusions, log-based metrics"
            echo -e "  ${GREEN}2.${NC} Cloud CDN        — Backend services, backend buckets, CDN status"
            echo -e "  ${GREEN}3.${NC} Cloud Scheduler  — Jobs, schedules, targets (HTTP, Pub/Sub, App Engine)"
            echo -e "  ${GREEN}4.${NC} Dialogflow CX    — Agents, display names, languages, timezones"
            echo -e "  ${GREEN}5.${NC} Pub/Sub          — Topics, subscriptions, retention, ack deadlines"
            echo -e "  ${GREEN}6.${NC} Vertex AI        — Endpoints, custom jobs, datasets, model registry"
            echo -e "  ${GREEN}7.${NC} Service Usage    — All enabled APIs/services with state"
            echo -e "  ${GREEN}8.${NC} Cloud Tasks      — Queues (rate limits, retry config), individual tasks"
            echo -e "  ${GREEN}9.${NC} Eventarc         — Triggers, event filters, destinations, channels"
            echo -e "  ${GREEN}10.${NC} Cloud Build     — Triggers, build history, source repos, substitutions"
            echo -e "  ${GREEN}11.${NC} Dataflow        — Jobs, type, region, SDK, autoscaling, current state"
            echo -e "  ${GREEN}12.${NC} Dataproc        — Clusters (node configs, image), jobs by type"
            ;;
    esac
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
    echo -e "Press Enter to continue..."
    read -r
}

show_menu_compute() {
    while true; do
        echo -e "\n${CYAN}=============== COMPUTE & KUBERNETES ===============${NC}"
        echo "1) Audit Compute Engine & Networking (VMs, Disks, VPCs)"
        echo "2) Audit Cloud Run Resources"
        echo "3) Audit Cloud Functions (v1 & v2)"
        echo "4) Audit App Engine Applications & Services"
        echo "5) Audit GKE Clusters & Node Pools"
        echo "6) Audit Cloud Composer (Managed Airflow)"
        echo "7) Audit Cloud Load Balancing (Forwarding Rules, Backends, SSL)"
        echo "8) Audit Cloud NAT (Routers & NAT Gateways)"
        echo "9) Audit Cloud DNS (Managed Zones & Records)"
        echo "10) Run all Compute & Kubernetes audits"
        echo "11) Back to Main Menu"
        echo "12) Exit"
        echo -e "${CYAN}====================================================${NC}"
        echo -e "  (${YELLOW}h${NC}=help ${YELLOW}m${NC}=main menu ${YELLOW}q${NC}=quit)"
        read -p "Select an option [1-12]: " SUB_OPT
        case $SUB_OPT in
            1) run_audit_gce ;;
            2) run_audit_run ;;
            3) run_audit_gcf ;;
            4) run_audit_gae ;;
            5) run_audit_gke ;;
            6) run_audit_composer ;;
            7) run_audit_lb ;;
            8) run_audit_nat ;;
            9) run_audit_dns ;;
            10)
                run_audit_gce
                run_audit_run
                run_audit_gcf
                run_audit_gae
                run_audit_gke
                run_audit_composer
                run_audit_lb
                run_audit_nat
                run_audit_dns
                ;;
            11|m|M) return ;;
            12|q|Q)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            h|H|\?) show_service_help compute ;;
            *) echo -e "${RED}Invalid option. Please try again.${NC}" ;;
        esac
    done
}

show_menu_storage() {
    while true; do
        echo -e "\n${CYAN}=============== STORAGE & DATABASES ===============${NC}"
        echo "1) Audit Cloud Storage (GCS) Resources"
        echo "2) GCS Analyser (size · folders · lifecycle · versioning · cost → PDF)"
        echo "3) Audit Cloud SQL Resources"
        echo "4) Audit Cloud Memorystore (Redis)"
        echo "5) Audit BigQuery (Datasets, Tables, Partitions, Jobs)"
        echo "6) Audit Artifact Registry Repositories"
        echo "7) Audit Firestore (Databases & Indexes)"
        echo "8) Audit Cloud Spanner (Instances, Databases, Backups)"
        echo "9) Audit AlloyDB (Clusters, Instances, Backups)"
        echo "10) Run all Storage & Database audits"
        echo "11) Back to Main Menu"
        echo "12) Exit"
        echo -e "${CYAN}===================================================${NC}"
        echo -e "  (${YELLOW}h${NC}=help ${YELLOW}m${NC}=main menu ${YELLOW}q${NC}=quit)"
        read -p "Select an option [1-12]: " SUB_OPT
        case $SUB_OPT in
            1) run_audit_gcs ;;
            2) run_gcs_analyser ;;
            3) run_audit_sql ;;
            4) run_audit_redis ;;
            5) run_audit_bq ;;
            6) run_audit_ar ;;
            7) run_audit_firestore ;;
            8) run_audit_spanner ;;
            9) run_audit_alloydb ;;
            10)
                run_audit_gcs
                run_audit_sql
                run_audit_redis
                run_audit_bq
                run_audit_ar
                run_audit_firestore
                run_audit_spanner
                run_audit_alloydb
                ;;
            11|m|M) return ;;
            12|q|Q)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            h|H|\?) show_service_help storage ;;
            *) echo -e "${RED}Invalid option. Please try again.${NC}" ;;
        esac
    done
}

show_menu_security() {
    while true; do
        echo -e "\n${CYAN}=============== IDENTITY & SECURITY ===============${NC}"
        echo "1) Audit IAM & Service Accounts (Keys, Roles)"
        echo "2) Audit Secret Manager Secrets & Versions"
        echo "3) Audit Cloud KMS (Key Rings & Crypto Keys)"
        echo "4) Audit VPC Service Controls (Service Perimeters)"
        echo "5) Audit Binary Authorization (Policy & Attestors)"
        echo "6) Audit Data Catalog (Tag Templates, Entry Groups, Entries)"
        echo "7) Run all Identity & Security audits"
        echo "8) Back to Main Menu"
        echo "9) Exit"
        echo -e "${CYAN}===================================================${NC}"
        echo -e "  (${YELLOW}h${NC}=help ${YELLOW}m${NC}=main menu ${YELLOW}q${NC}=quit)"
        read -p "Select an option [1-9]: " SUB_OPT
        case $SUB_OPT in
            1) run_audit_iam ;;
            2) run_audit_sm ;;
            3) run_audit_kms ;;
            4) run_audit_vpc_sc ;;
            5) run_audit_binauthz ;;
            6) run_audit_datacatalog ;;
            7)
                run_audit_iam
                run_audit_sm
                run_audit_kms
                run_audit_vpc_sc
                run_audit_binauthz
                run_audit_datacatalog
                ;;
            8|m|M) return ;;
            9|q|Q)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            h|H|\?) show_service_help security ;;
            *) echo -e "${RED}Invalid option. Please try again.${NC}" ;;
        esac
    done
}

show_menu_ops() {
    while true; do
        echo -e "\n${CYAN}============= OPERATIONS & INTEGRATION =============${NC}"
        echo "1) Audit Cloud Logging (Sinks, Buckets, Exclusions, Metrics)"
        echo "2) Audit Cloud CDN (Backend Services & Buckets)"
        echo "3) Audit Cloud Scheduler Jobs"
        echo "4) Audit Dialogflow CX Agents (Agent Platform)"
        echo "5) Audit Pub/Sub Topics & Subscriptions"
        echo "6) Audit Vertex AI (Endpoints, Custom Jobs, Datasets)"
        echo "7) Audit Enabled APIs & Services (Service Usage)"
        echo "8) Audit Cloud Tasks (Queues & Tasks)"
        echo "9) Audit Eventarc (Triggers & Channels)"
        echo "10) Audit Cloud Build (Triggers & Builds)"
        echo "11) Audit Dataflow (Jobs)"
        echo "12) Audit Dataproc (Clusters & Jobs)"
        echo "13) Run all Operations & Integration audits"
        echo "14) Back to Main Menu"
        echo "15) Exit"
        echo -e "${CYAN}====================================================${NC}"
        echo -e "  (${YELLOW}h${NC}=help ${YELLOW}m${NC}=main menu ${YELLOW}q${NC}=quit)"
        read -p "Select an option [1-15]: " SUB_OPT
        case $SUB_OPT in
            1) run_audit_logging ;;
            2) run_audit_cdn ;;
            3) run_audit_scheduler ;;
            4) run_audit_agent ;;
            5) run_audit_pubsub ;;
            6) run_audit_vertex ;;
            7) run_audit_su ;;
            8) run_audit_tasks ;;
            9) run_audit_eventarc ;;
            10) run_audit_cloudbuild ;;
            11) run_audit_dataflow ;;
            12) run_audit_dataproc ;;
            13)
                run_audit_logging
                run_audit_cdn
                run_audit_scheduler
                run_audit_agent
                run_audit_pubsub
                run_audit_vertex
                run_audit_su
                run_audit_tasks
                run_audit_eventarc
                run_audit_cloudbuild
                run_audit_dataflow
                run_audit_dataproc
                ;;
            14|m|M) return ;;
            15|q|Q)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            h|H|\?) show_service_help ops ;;
            *) echo -e "${RED}Invalid option. Please try again.${NC}" ;;
        esac
    done
}

show_menu_auth() {
    while true; do
        echo -e "\n${CYAN}============= GCP AUTHENTICATION MANAGEMENT =============${NC}"
        echo "1) List Local Authenticated Accounts"
        echo "2) List Accessible GCP Projects"
        echo "3) Login to a New Account"
        echo "4) Logout / Revoke Active Credentials"
        echo "5) Back to Main Menu"
        echo "6) Exit"
        echo -e "${CYAN}=========================================================${NC}"
        echo -e "  (${YELLOW}m${NC}=main menu ${YELLOW}q${NC}=quit)"
        read -p "Select an option [1-6]: " SUB_OPT
        case $SUB_OPT in
            1)
                echo -e "\n${BLUE}Local Authenticated Accounts:${NC}"
                gcloud auth list
                ;;
            2)
                echo -e "\n${BLUE}Accessible GCP Projects:${NC}"
                gcloud projects list
                ;;
            3)
                echo -e "\n${BLUE}Logging into new account...${NC}"
                echo "1. Authenticating User Account:"
                gcloud auth login
                echo "2. Setting up Application Default Credentials (ADC):"
                gcloud auth application-default login
                ;;
            4)
                read -p "Are you sure you want to revoke all active credentials? [y/N]: " CONFIRM
                if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
                    echo -e "\n${BLUE}Revoking active credentials...${NC}"
                    gcloud auth revoke --all
                    gcloud auth application-default revoke --quiet 2>/dev/null
                    echo -e "${GREEN}✅ All active credentials revoked.${NC}"
                else
                    echo "Revocation cancelled."
                fi
                ;;
            5|m|M) return ;;
            6|q|Q)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            *) echo -e "${RED}Invalid option. Please try again.${NC}" ;;
        esac
    done
}

# 7. Interactive Menu
while true; do
    echo -e "\n${CYAN}================= MAIN MENU =================${NC}"
    echo "1) Compute & Kubernetes Audits"
    echo "2) Storage & Database Audits"
    echo "3) Identity & Security Audits"
    echo "4) Operations & Integration Audits"
    echo "5) Run ALL Audits (Full Scan)"
    echo "6) Manage GCP Authentication (Login, Logout, List Accounts/Projects)"
    echo "7) Exit"
    echo -e "${CYAN}=============================================${NC}"
    echo -e "  (${YELLOW}q${NC}=quit)"
    read -p "Select an option [1-7]: " OPTION

    case $OPTION in
        1) show_menu_compute ;;
        2) show_menu_storage ;;
        3) show_menu_security ;;
        4) show_menu_ops ;;
        5) run_audit_all ;;
        6) show_menu_auth ;;
        7|q|Q)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            ;;
    esac
done
