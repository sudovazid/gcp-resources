"""
GCS Bucket - Per Folder File Type & Size Analyzer
===================================================
Iterates every folder in a GCS bucket and shows:
  - File types per folder with sizes
  - Folder totals
  - Grand total summary

Usage:
    python3 gcs_folder_analysis.py

Requirements:
    pip install google-cloud-storage tabulate

Auth:
    gcloud auth application-default login
"""

import os as _os

from google.cloud import storage
from collections import defaultdict
import csv
import sys
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BUCKET_NAME  = _os.environ.get("GCS_BUCKET_NAME", "")
PROJECT_ID   = _os.environ.get("GCP_PROJECT_ID", "")
FOLDER_DEPTH = 2          # How many folder levels to group by (1 = top level only)
PREFIX       = ""         # Limit to a specific path, e.g. "rotation-fix/" or leave ""
SAVE_CSV     = True       # Save results to CSV file
CSV_OUTPUT   = f"bucket_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
# ─────────────────────────────────────────────────────────────────────────────


def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def get_folder(blob_name, depth):
    """Get the folder path up to a given depth."""
    parts = blob_name.split("/")
    if len(parts) <= depth:
        return "/".join(parts[:-1]) or "(root)"
    return "/".join(parts[:depth])


def get_extension(blob_name):
    """Get file extension from full blob path."""
    filename = blob_name.split("/")[-1]
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return "(no ext)"


def scan_bucket(bucket_name, prefix, depth):
    """Scan all blobs and group by folder + extension."""
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)

    # folder -> extension -> {count, size}
    folder_data  = defaultdict(lambda: defaultdict(lambda: {"count": 0, "size": 0}))
    grand_total  = {"count": 0, "size": 0}
    folder_totals = defaultdict(lambda: {"count": 0, "size": 0})

    print(f"\n  Scanning gs://{bucket_name}/{prefix}")
    print(f"  Grouping by first {depth} folder level(s)\n")

    blobs   = bucket.list_blobs(prefix=prefix)
    counter = 0

    for blob in blobs:
        size   = blob.size or 0
        folder = get_folder(blob.name, depth)
        ext    = get_extension(blob.name)

        folder_data[folder][ext]["count"] += 1
        folder_data[folder][ext]["size"]  += size
        folder_totals[folder]["count"]    += 1
        folder_totals[folder]["size"]     += size
        grand_total["count"]              += 1
        grand_total["size"]               += size

        counter += 1
        if counter % 50000 == 0:
            print(f"  Scanned {counter:,} files ... "
                  f"({len(folder_data)} folders found so far)")

    print(f"\n  Done — scanned {counter:,} files across "
          f"{len(folder_data)} folders\n")

    return folder_data, folder_totals, grand_total


def print_report(folder_data, folder_totals, grand_total):
    """Print a clean per-folder report."""

    sep  = "=" * 80
    line = "-" * 80

    print(sep)
    print(f"  BUCKET  :  gs://{BUCKET_NAME}")
    print(f"  TOTAL   :  {grand_total['count']:,} files  "
          f"|  {format_size(grand_total['size'])}")
    print(f"  FOLDERS :  {len(folder_data)}")
    print(sep)

    # Sort folders by total size (biggest first)
    sorted_folders = sorted(
        folder_totals.items(),
        key=lambda x: x[1]["size"],
        reverse=True
    )

    for folder, totals in sorted_folders:
        pct = (totals["size"] / grand_total["size"] * 100) if grand_total["size"] else 0

        print(f"\n  📂  {folder}/")
        print(f"      Total: {totals['count']:,} files  |  "
              f"{format_size(totals['size'])}  ({pct:.1f}% of bucket)")
        print(f"      {'Extension':<18} {'Count':>10} {'Size':>14} {'Avg Size':>12}")
        print(f"      {line[:56]}")

        # Sort extensions by size within this folder
        exts = sorted(
            folder_data[folder].items(),
            key=lambda x: x[1]["size"],
            reverse=True
        )

        for ext, data in exts:
            avg = data["size"] / data["count"] if data["count"] else 0
            print(f"      {ext:<18} {data['count']:>10,} "
                  f"{format_size(data['size']):>14} "
                  f"{format_size(avg):>12}")

    # Grand summary table
    print(f"\n\n{sep}")
    print("  GRAND SUMMARY — ALL FILE TYPES ACROSS ENTIRE BUCKET")
    print(sep)

    all_exts = defaultdict(lambda: {"count": 0, "size": 0})
    for folder, exts in folder_data.items():
        for ext, data in exts.items():
            all_exts[ext]["count"] += data["count"]
            all_exts[ext]["size"]  += data["size"]

    print(f"\n  {'Extension':<18} {'Count':>10} {'Total Size':>14} "
          f"{'% of bucket':>12} {'Avg Size':>12}")
    print(f"  {line[:70]}")

    for ext, data in sorted(all_exts.items(),
                             key=lambda x: x[1]["size"], reverse=True):
        pct = (data["size"] / grand_total["size"] * 100) if grand_total["size"] else 0
        avg = data["size"] / data["count"] if data["count"] else 0
        print(f"  {ext:<18} {data['count']:>10,} "
              f"{format_size(data['size']):>14} "
              f"{pct:>11.1f}% "
              f"{format_size(avg):>12}")

    print(f"\n  {'TOTAL':<18} {grand_total['count']:>10,} "
          f"{format_size(grand_total['size']):>14}")
    print(sep)


def save_csv(folder_data, folder_totals, grand_total, filename):
    """Save detailed results to CSV."""
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Folder", "Extension", "File Count",
            "Total Size (Bytes)", "Total Size (Human)", "Avg Size (Bytes)"
        ])

        sorted_folders = sorted(
            folder_totals.items(),
            key=lambda x: x[1]["size"],
            reverse=True
        )

        for folder, _ in sorted_folders:
            exts = sorted(
                folder_data[folder].items(),
                key=lambda x: x[1]["size"],
                reverse=True
            )
            for ext, data in exts:
                avg = data["size"] // data["count"] if data["count"] else 0
                writer.writerow([
                    folder,
                    ext,
                    data["count"],
                    data["size"],
                    format_size(data["size"]),
                    avg
                ])

        # Summary row
        writer.writerow([])
        writer.writerow(["TOTAL", "ALL", grand_total["count"],
                         grand_total["size"], format_size(grand_total["size"]), ""])

    print(f"\n  CSV saved to: {filename}")


def main():
    if not PROJECT_ID or not BUCKET_NAME:
        print("\n  Error: GCP_PROJECT_ID and GCS_BUCKET_NAME environment variables must be set.")
        print("  Usage: GCP_PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket python3 file_size_analyser.py")
        return
    try:
        folder_data, folder_totals, grand_total = scan_bucket(
            BUCKET_NAME, PREFIX, FOLDER_DEPTH
        )
        print_report(folder_data, folder_totals, grand_total)

        if SAVE_CSV:
            save_csv(folder_data, folder_totals, grand_total, CSV_OUTPUT)

    except Exception as e:
        print(f"\n  Error: {e}")
        print("\n  Checklist:")
        print("  1. Run: gcloud auth application-default login")
        print("  2. Run: pip install google-cloud-storage")
        print(f"  3. Confirm bucket name: {BUCKET_NAME}")
        print(f"  4. Confirm project:     {PROJECT_ID}")
        sys.exit(1)


if __name__ == "__main__":
    main()
