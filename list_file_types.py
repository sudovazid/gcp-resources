"""
GCS Bucket - List Unique File Types
====================================
Handles deep folder structures (UUID folders etc.)
Samples files from across the bucket to find all file extensions.

Usage:
    python3 list_file_types.py

Requirements:
    pip install google-cloud-storage

Auth:
    gcloud auth application-default login
"""

import os

from google.cloud import storage

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PROJECT_ID       = os.environ.get("GCP_PROJECT_ID", "")
BUCKET_NAME      = os.environ.get("GCS_BUCKET_NAME", "")
MAX_FOLDERS      = 50    # how many top-level folders to sample from
FILES_PER_FOLDER = 20    # files to check per folder
# ─────────────────────────────────────────────────────────────────────────────


def get_extension(blob_name):
    filename = blob_name.split("/")[-1]
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return None


def get_top_level_folders(bucket):
    """Get all top-level folder prefixes using delimiter."""
    iterator = bucket.client.list_blobs(
        bucket, delimiter="/", max_results=1000
    )
    list(iterator)  # must consume to populate .prefixes
    return list(iterator.prefixes)


def main():
    if not PROJECT_ID or not BUCKET_NAME:
        print("\n  Error: GCP_PROJECT_ID and GCS_BUCKET_NAME environment variables must be set.")
        print("  Usage: GCP_PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket python3 list_file_types.py")
        return
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    print(f"\n  Bucket: gs://{BUCKET_NAME}\n")

    extensions = {}   # ext -> example full path

    # ── Step 1: Sample files with no prefix (catches root-level files) ──────
    print("  Checking root-level files...")
    for blob in bucket.client.list_blobs(bucket, max_results=200):
        ext = get_extension(blob.name)
        if ext and ext not in extensions:
            extensions[ext] = blob.name

    # ── Step 2: Get top-level folders (could be UUIDs, named folders, etc.) ─
    print("  Getting top-level folders...")
    folders = get_top_level_folders(bucket)
    print(f"  Found {len(folders)} top-level folders\n")

    # ── Step 3: Sample files from each folder (recursive, no delimiter) ──────
    sampled = 0
    for folder in folders[:MAX_FOLDERS]:
        blobs = bucket.client.list_blobs(
            bucket,
            prefix=folder,
            max_results=FILES_PER_FOLDER
        )
        for blob in blobs:
            ext = get_extension(blob.name)
            if ext and ext not in extensions:
                extensions[ext] = blob.name
        sampled += 1
        if sampled % 10 == 0:
            print(f"  Sampled {sampled}/{min(len(folders), MAX_FOLDERS)} "
                  f"folders — {len(extensions)} file type(s) found so far...")

    # ── Step 4: Print results ─────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  FILE TYPES IN gs://{BUCKET_NAME}")
    print("=" * 60)

    if not extensions:
        print("\n  No files with extensions found in sample.")
        print("  Try increasing MAX_FOLDERS or FILES_PER_FOLDER.")
    else:
        print(f"\n  {'Extension':<12}  Example file path")
        print(f"  {'-' * 56}")
        for ext in sorted(extensions.keys()):
            path = extensions[ext]
            # Show last part of path for readability
            display = path if len(path) <= 55 else "..." + path[-52:]
            print(f"  {ext:<12}  {display}")

    print(f"\n  Total: {len(extensions)} unique file type(s)")
    print(f"  Sampled from {sampled} folders "
          f"({FILES_PER_FOLDER} files each)\n")

    if len(folders) > MAX_FOLDERS:
        print(f"  Note: {len(folders) - MAX_FOLDERS} folders were not sampled.")
        print(f"  Increase MAX_FOLDERS to check more.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n  Error: {e}")
        print("  1. Run: gcloud auth application-default login")
        print("  2. Run: pip install google-cloud-storage")
