# ☁️ GCS Analyser

Scans **Google Cloud Storage** buckets and produces a polished **PDF** (plus optional CSV) covering, at the **file**, **folder**, and **bucket** level:

1. **Inventory** — object/folder/bucket sizes and grand totals.
2. **Lifecycle & versioning** — bucket lifecycle rules + per-object **live vs noncurrent** (version) state, with versioning on/off per bucket.
3. **Cost** — estimated **monthly at-rest storage cost** per file, folder, bucket, and storage class.

The PDF has KPI tiles, charts (cost-by-bucket, size-by-class), an all-buckets summary with totals, and a per-bucket section (details, lifecycle, storage-class split, folder breakdown, largest files).

> Per-file cost for *every* object goes in the CSV (`--csv`); the PDF lists the **largest N** files per bucket plus the **folder aggregates** that cover all objects — so it stays readable even on huge buckets.

## Setup
```bash
pip install -r requirements.txt          # google-cloud-storage + reportlab
gcloud auth application-default login     # one-time auth
```

## Run
```bash
./run.sh                                  # uses GCP_PROJECT_ID env var or prompts
./run.sh -p <your-project-id> --csv       # + full per-object CSV
python3 gcs_analyser.py --project <your-project-id> --buckets my-bucket,other-bucket
python3 gcs_analyser.py --project <your-project-id> --prefix-depth 2 --top-files 25
```

### Flags
| Flag | Default | Meaning |
|------|---------|---------|
| `--project` | *(required)* | GCP project ID |
| `--buckets` | *(all)* | comma-separated bucket names |
| `--prefix-depth` | `1` | path segments that define a "folder" (`a/b/c.txt` at depth 2 → folder `a/b/`) |
| `--top-files` | `15` | largest N files listed per bucket in the PDF |
| `--workers` | `8` | buckets scanned in parallel |
| `--output` | *(timestamped)* | PDF path |
| `--csv` | off | also write full per-object CSV |

## How it works / speed
- Lists objects with **`versions=True`** so noncurrent (superseded/soft-deleted) versions are counted and sized — that's the hidden cost versioning creates.
- Requests only the fields it needs (`name,size,storageClass,updated,timeCreated,timeDeleted,generation`) and scans buckets **concurrently** (`ThreadPoolExecutor`).
- Per-object listing is required because **lifecycle/versioning/per-file cost** can't come from Cloud Monitoring (which only gives bucket×class totals — see the sibling `gcs_classes_analysis.py` for the instant bucket-level view on petabyte buckets).

## Cost model — read this
`pricing.py` holds **list at-rest storage prices** (USD/GB-month) by location type × storage class. Cost = `size_GB × price`. It **excludes** operations (Class A/B), network egress, retrieval, and early-delete (minimum-duration) fees. Prices vary by region — **edit `pricing.py`** to match your region/contract for accurate numbers.

## Files
| File | Role |
|------|------|
| `gcs_analyser.py` | CLI + concurrent scan + aggregation |
| `report.py` | reportlab PDF (tables, charts, per-bucket sections) |
| `pricing.py` | editable storage-class price table |
| `run.sh` | auth check + wrapper |

## Required IAM
`roles/storage.objectViewer` + `roles/storage.bucketViewer` (or `roles/storage.admin`) on the buckets/project you scan.
