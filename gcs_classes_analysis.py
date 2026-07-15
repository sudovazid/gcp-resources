"""
GCS Bucket Storage Breakdown via Cloud Monitoring
==================================================
Gets bucket size broken down by:
  - Bucket name
  - Storage class (REGIONAL, NEARLINE, COLDLINE, ARCHIVE)
  - Object type (live-object, noncurrent-object, soft-deleted-object)

This reads from Cloud Monitoring metrics — no object iteration needed.
Works for petabyte-scale buckets instantly.

Usage:
    python3 gcs_storage_breakdown.py

Requirements:
    pip install google-cloud-monitoring

Auth:
    gcloud auth application-default login
"""

import os

from google.cloud import monitoring_v3
import time
from collections import defaultdict
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PROJECT_ID    = os.environ.get("GCP_PROJECT_ID", "")
BUCKET_FILTER = ""        # filter to specific bucket e.g. "my-bucket"
                          # leave empty to get ALL buckets
SAVE_CSV      = True
CSV_FILE      = f"gcs_breakdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
# ─────────────────────────────────────────────────────────────────────────────


def format_size(size_bytes):
    """Convert bytes to human-readable size (MiB/GiB/TiB/PiB)."""
    if size_bytes == 0:
        return "0 B"
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.3f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.3f}PiB"


def fetch_storage_breakdown(project_id, bucket_filter=""):
    """Fetch total_bytes metric from Cloud Monitoring broken down by class + type."""
    client       = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    # Use last 10 minutes to get latest data point
    now   = time.time()
    interval = monitoring_v3.TimeInterval({
        "end_time":   {"seconds": int(now)},
        "start_time": {"seconds": int(now - 600)},
    })

    # Build filter
    metric_filter = 'metric.type = "storage.googleapis.com/storage/total_bytes"'
    if bucket_filter:
        metric_filter += f' AND resource.labels.bucket_name = "{bucket_filter}"'

    print(f"\n  Fetching Cloud Monitoring data for project: {project_id}")
    if bucket_filter:
        print(f"  Bucket filter: {bucket_filter}")
    print(f"  Metric: storage.googleapis.com/storage/total_bytes\n")

    results = client.list_time_series(
        request={
            "name":     project_name,
            "filter":   metric_filter,
            "interval": interval,
            "view":     monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )

    rows = []
    for ts in results:
        bucket_name   = ts.resource.labels.get("bucket_name", "unknown")
        storage_class = ts.metric.labels.get("storage_class", "unknown")
        obj_type      = ts.metric.labels.get("type", "unknown")

        # Get the most recent data point
        if ts.points:
            latest = ts.points[0]
            # total_bytes comes as a double value
            size_bytes = latest.value.double_value
            if size_bytes == 0:
                size_bytes = float(latest.value.int64_value)

            rows.append({
                "bucket_name":   bucket_name,
                "storage_class": storage_class,
                "type":          obj_type,
                "size_bytes":    size_bytes,
                "size_human":    format_size(size_bytes),
            })

    return rows


def print_table(rows):
    """Print results as a formatted table matching the requested output."""
    if not rows:
        print("  No data found. Check project ID, bucket name, or auth.")
        return

    # Sort by bucket name, then by size descending
    rows.sort(key=lambda x: (x["bucket_name"], -x["size_bytes"]))

    # Column widths
    w_bucket  = max(len(r["bucket_name"])   for r in rows) + 2
    w_class   = max(len(r["storage_class"]) for r in rows) + 2
    w_type    = max(len(r["type"])          for r in rows) + 2
    w_size    = max(len(r["size_human"])    for r in rows) + 2

    sep = "-" * (w_bucket + w_class + w_type + w_size + 6)

    # Header
    print(sep)
    print(
        f"{'Bucket Name':<{w_bucket}}"
        f"{'Storage Class':<{w_class}}"
        f"{'Type':<{w_type}}"
        f"{'Size':>{w_size}}"
    )
    print(sep)

    # Rows — add blank line between buckets
    current_bucket = None
    bucket_totals  = defaultdict(float)
    grand_total    = 0.0

    for r in rows:
        if current_bucket and current_bucket != r["bucket_name"]:
            # Print bucket subtotal
            print(
                f"{'':>{w_bucket}}"
                f"{'':>{w_class}}"
                f"{'BUCKET TOTAL':<{w_type}}"
                f"{format_size(bucket_totals[current_bucket]):>{w_size}}"
            )
            print()

        current_bucket = r["bucket_name"]
        bucket_totals[r["bucket_name"]] += r["size_bytes"]
        grand_total += r["size_bytes"]

        print(
            f"{r['bucket_name']:<{w_bucket}}"
            f"{r['storage_class']:<{w_class}}"
            f"{r['type']:<{w_type}}"
            f"{r['size_human']:>{w_size}}"
        )

    # Last bucket subtotal
    if current_bucket:
        print(
            f"{'':>{w_bucket}}"
            f"{'':>{w_class}}"
            f"{'BUCKET TOTAL':<{w_type}}"
            f"{format_size(bucket_totals[current_bucket]):>{w_size}}"
        )

    # Grand total
    print()
    print(sep)
    print(
        f"{'GRAND TOTAL':<{w_bucket}}"
        f"{'':>{w_class}}"
        f"{'ALL BUCKETS':<{w_type}}"
        f"{format_size(grand_total):>{w_size}}"
    )
    print(sep)

    # Summary by object type
    print("\n  SUMMARY BY OBJECT TYPE\n")
    type_totals = defaultdict(float)
    for r in rows:
        type_totals[r["type"]] += r["size_bytes"]

    for obj_type, size in sorted(type_totals.items(),
                                  key=lambda x: -x[1]):
        pct = (size / grand_total * 100) if grand_total else 0
        print(f"  {obj_type:<30} {format_size(size):>12}  ({pct:.1f}%)")

    print()


def save_csv(rows, filename):
    """Save results to CSV."""
    import csv
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "bucket_name", "storage_class", "type", "size_bytes", "size_human"
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved to: {filename}")


def main():
    if not PROJECT_ID:
        print("\n  Error: GCP_PROJECT_ID environment variable not set.")
        print("  Usage: GCP_PROJECT_ID=my-project python3 gcs_classes_analysis.py")
        return
    try:
        rows = fetch_storage_breakdown(PROJECT_ID, BUCKET_FILTER)
        print_table(rows)

        if SAVE_CSV and rows:
            save_csv(rows, CSV_FILE)

    except Exception as e:
        print(f"\n  Error: {e}")
        print("\n  Checklist:")
        print("  1. gcloud auth application-default login")
        print("  2. pip install google-cloud-monitoring")
        print(f"  3. Confirm project: {PROJECT_ID}")
        print("  4. Monitoring API enabled in the project")


if __name__ == "__main__":
    main()
