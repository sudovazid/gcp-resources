# GCP Resource Auditor

A comprehensive toolkit for auditing Google Cloud Platform resources across **35 services**. Generates detailed reports in CSV, Excel, and PDF formats.

## Features

- **Interactive mode** — menu-driven audit selection via `gcp_core.sh` with keyboard shortcuts
- **Batch mode** — non-interactive full scan via `run_full_audit.sh` with `EXPORT_FORMATS` override
- **Config persistence** — last-used project and export format saved to `~/.config/gcp-auditor/config`
- **API enablement detection** — auto-detects disabled APIs and suggests `gcloud services enable` commands
- **Progress tracking** — live counter, elapsed time, and per-service pass/fail summary for full audits
- **Export format menu** — choose per-audit: CSV only, Excel only, PDF only, or all formats
- **Deep GCS analysis** — per-object inventory, lifecycle, versioning, and cost estimates (PDF)
- **Supports 35 GCP services** — Compute, GKE, Cloud Run, Cloud SQL, GCS, BigQuery, Pub/Sub, IAM, Secret Manager, KMS, and more
- **Service help system** — press `?` or `h` in any menu for a categorized list of all audit options
- **Keyboard shortcuts** — `h`/`?` (help), `m` (main menu), `q` (quit) available in every submenu

## Quick Start

```bash
# Prerequisites
gcloud auth application-default login

# Interactive audit
./gcp_core.sh

# Non-interactive full audit
export GCP_PROJECT_ID=my-project
./run_full_audit.sh
```

## Usage

### Interactive Mode

```bash
./gcp_core.sh
```

Launches a menu-driven interface organized into four categories:

| Menu | Services |
|------|----------|
| **Compute & Networking** | Compute Engine, Cloud Run, Cloud Functions, App Engine, GKE, Composer, Load Balancing, NAT, DNS |
| **Storage & Data** | GCS, Cloud SQL, Memorystore, BigQuery, Artifact Registry, Firestore, Spanner, AlloyDB, Data Catalog |
| **Identity & Security** | IAM, Secret Manager, KMS, VPC Service Controls, Binary Authorization, Cloud Build |
| **Operations & Integration** | Pub/Sub, Scheduler, Tasks, Eventarc, Logging, CDN, Gemini Enterprise Agent Platform (Dialogflow CX), Vertex AI, Service Usage, Dataflow, Dataproc |

Available in all menus:
- `1-9` — run a single service audit
- `a` — run all services in that category
- `h` or `?` — show service help
- `m` — return to main menu
- `q` — quit

### Batch Mode

```bash
export GCP_PROJECT_ID=my-project
./run_full_audit.sh
```

Runs all 35 service audits sequentially without interaction. Override the export format:

```bash
EXPORT_FORMATS="xlsx-only" ./run_full_audit.sh
```

Valid formats: `csv`, `xlsx-only`, `pdf-only`, `all` (default).

### Format Selection

When running any audit, you are prompted to choose an export format:

| Option | Format | Example Output |
|--------|--------|---------------|
| 1 | CSV only | `my-project_gcs_resource.csv` |
| 2 | Excel only | `my-project_gcs_resource.xlsx` |
| 3 | PDF only | `my-project_gcs_resource.pdf` |
| 4 | All formats | CSV + XLSX + PDF |

The last selection is persisted in `~/.config/gcp-auditor/config` across sessions.

### GCS Analyser (Deep Analysis)

```bash
cd gcs-analyser
pip install -r requirements.txt
python3 gcs_analyser.py --project my-project
```

Produces a PDF with per-bucket inventory, storage-class breakdown, folder aggregates, lifecycle rules, versioning state, and estimated monthly cost.

### Standalone Utility Scripts

```bash
# GCS storage breakdown by class via Cloud Monitoring
GCP_PROJECT_ID=my-project python3 gcs_classes_analysis.py

# List file types in a GCS bucket
GCP_PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket python3 list_file_types.py

# Analyse file sizes per folder in a bucket
GCP_PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket python3 file_size_analyser.py
```

## Configuration

Settings persist across sessions in `~/.config/gcp-auditor/config`:

```
LAST_PROJECT=my-project
EXPORT_FORMATS=all
```

Clearing this file resets to default prompts.

## Supported Services

| Category | Services |
|---|---|
| **Compute & Networking** | Compute Engine, Cloud Run, Cloud Functions, App Engine, GKE, Cloud Composer, Cloud Load Balancing, Cloud NAT, Cloud DNS |
| **Storage & Data** | Cloud Storage (GCS), Cloud SQL, Memorystore (Redis), BigQuery, Artifact Registry, Firestore, Cloud Spanner, AlloyDB, Data Catalog |
| **Identity & Security** | IAM, Secret Manager, Cloud KMS, VPC Service Controls, Binary Authorization, Cloud Build |
| **Operations & Integration** | Pub/Sub, Cloud Logging, Cloud CDN, Cloud Scheduler, Cloud Tasks, Eventarc, Gemini Enterprise Agent Platform (Dialogflow CX), Vertex AI, Service Usage, Dataflow, Dataproc |

## Output

All reports are saved to `./output/` with filenames prefixed by the project ID and service name.

## IAM Requirements

The auditing identity needs the following roles (or equivalent custom roles):

- `roles/viewer` on the project (for most read-only operations)
- `roles/storage.objectViewer` + `roles/storage.bucketViewer` for GCS deep analysis
- `roles/monitoring.viewer` for Cloud Monitoring based analysis

## Project Structure

```
├── gcp_core.sh                      # Interactive audit launcher
├── run_full_audit.sh                # Batch audit runner
├── gcs_classes_analysis.py          # GCS breakdown by storage class
├── list_file_types.py               # GCS file-type sampler
├── file_size_analyser.py            # Per-folder file size analyser
├── requirements.txt                 # Python dependencies
├── LICENSE                          # Apache 2.0
├── CONTRIBUTING.md                  # Contribution guidelines
├── CODE_OF_CONDUCT.md               # Code of conduct
├── SECURITY.md                      # Security policy
├── CHANGELOG.md                     # Version history
├── utils/                           # Export conversion utilities
│   └── export_converter.py          # CSV → XLSX/PDF converter
├── gcs-analyser/                    # Deep GCS analysis (PDF reports)
├── agent-platform/                  # Gemini Enterprise Agent Platform (Dialogflow CX) audit
├── alloydb/                         # AlloyDB audit
├── app_engine/                      # App Engine audit
├── artifact_registry/               # Artifact Registry audit
├── bigquery/                        # BigQuery audit
├── binary_authorization/            # Binary Authorization audit
├── cloud_build/                     # Cloud Build audit
├── cloud_cdn/                       # Cloud CDN audit
├── cloud_dns/                       # Cloud DNS audit
├── cloud_functions/                 # Cloud Functions audit
├── cloud_load_balancing/            # Cloud Load Balancing audit
├── cloud_logging/                   # Cloud Logging audit
├── cloud_nat/                       # Cloud NAT audit
├── cloud_run/                       # Cloud Run audit
├── cloud_scheduler/                 # Cloud Scheduler audit
├── cloud_spanner/                   # Cloud Spanner audit
├── cloud_sql/                       # Cloud SQL audit
├── cloud_tasks/                     # Cloud Tasks audit
├── composer/                        # Cloud Composer audit
├── compute_engine/                  # Compute Engine audit
├── data_catalog/                    # Data Catalog audit
├── dataflow/                        # Dataflow audit
├── dataproc/                        # Dataproc audit
├── eventarc/                        # Eventarc audit
├── firestore/                       # Firestore audit
├── gcs/                             # Cloud Storage (GCS) audit
├── gke/                             # GKE audit
├── iam/                             # IAM & Service Accounts audit
├── kms/                             # Cloud KMS audit
├── pubsub/                          # Pub/Sub audit
├── redis/                           # Memorystore (Redis) audit
├── secret_manager/                  # Secret Manager audit
├── service_usage/                   # Service Usage (Enabled APIs) audit
├── vertex_ai/                       # Vertex AI audit
├── vpc_sc/                          # VPC Service Controls audit
└── output/                          # Generated audit reports
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
