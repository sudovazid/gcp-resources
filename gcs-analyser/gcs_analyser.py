"""
GCS Analyser
============
Scans Google Cloud Storage buckets and reports, per **file**, per **folder**
(prefix) and per **bucket**:
  1. Inventory — object/folder/bucket sizes and totals.
  2. Lifecycle & versioning — bucket rules + per-object live vs noncurrent state.
  3. Cost — estimated monthly at-rest storage cost (see pricing.py).

Outputs a polished **PDF** (tables + charts + per-bucket summary) and an
optional full per-object **CSV**.

Usage:
    python3 gcs_analyser.py --project my-project
    python3 gcs_analyser.py --project my-project --buckets my-bucket,other-bucket
    python3 gcs_analyser.py --project my-project --prefix-depth 2 --top-files 25 --csv

Auth (once):
    gcloud auth application-default login

Requirements:
    pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone

from google.cloud import storage

import pricing
import report

# ─── CONFIG (override via CLI flags) ──────────────────────────────────────────
PROJECT_ID    = ""                  # default GCP project (required via --project flag)
PREFIX_DEPTH  = 1                  # how many path segments define a "folder"
TOP_FILES     = 15                 # largest N files listed per bucket in the PDF
WORKERS       = 8                  # buckets scanned in parallel
# ──────────────────────────────────────────────────────────────────────────────

# Only fetch the fields we need — keeps listing fast on huge buckets.
_BLOB_FIELDS = (
    "items(name,size,storageClass,updated,timeCreated,timeDeleted,generation),"
    "nextPageToken"
)


def format_size(size_bytes: float) -> str:
    """Human-readable size (matches the style of gcs_classes_analysis.py)."""
    if not size_bytes:
        return "0 B"
    size = float(size_bytes)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} EiB"


@dataclass
class ObjectRow:
    bucket: str
    name: str
    folder: str
    size: int
    storage_class: str
    updated: str
    state: str          # "live" | "noncurrent"
    cost_month: float


@dataclass
class FolderAgg:
    folder: str
    count: int = 0
    size: int = 0
    cost_month: float = 0.0


@dataclass
class BucketReport:
    name: str
    location: str
    location_type: str
    default_storage_class: str
    versioning_enabled: bool
    lifecycle_rules: list = field(default_factory=list)
    created: str = ""
    object_count: int = 0
    live_count: int = 0
    noncurrent_count: int = 0
    total_size: int = 0
    live_size: int = 0
    noncurrent_size: int = 0
    cost_month: float = 0.0
    class_breakdown: dict = field(default_factory=dict)     # class -> {size,count,cost}
    folders: list = field(default_factory=list)             # list[FolderAgg]
    top_files: list = field(default_factory=list)           # list[ObjectRow]
    objects: list = field(default_factory=list)             # full list (for CSV)
    error: str = ""


def _folder_of(name: str, depth: int) -> str:
    parts = name.split("/")
    if len(parts) <= depth:                       # object lives at/above this depth
        return "/".join(parts[:-1]) + "/" if len(parts) > 1 else "(root)"
    return "/".join(parts[:depth]) + "/"


def _lifecycle_summary(rules) -> list[str]:
    """Turn raw lifecycle rules into short human strings."""
    out = []
    for r in rules or []:
        action = r.get("action", {})
        cond = r.get("condition", {})
        act = action.get("type", "?")
        if act == "SetStorageClass":
            act = f"→ {action.get('storageClass', '?')}"
        elif act == "Delete":
            act = "Delete"
        conds = []
        if "age" in cond:
            conds.append(f"age≥{cond['age']}d")
        if cond.get("isLive") is not None:
            conds.append("live" if cond["isLive"] else "noncurrent")
        if "numNewerVersions" in cond:
            conds.append(f">{cond['numNewerVersions']} newer")
        if "matchesStorageClass" in cond:
            conds.append("class∈" + ",".join(cond["matchesStorageClass"]))
        if "createdBefore" in cond:
            conds.append(f"before {cond['createdBefore']}")
        out.append(f"{act} when " + (", ".join(conds) if conds else "always"))
    return out


def scan_bucket(client: storage.Client, bucket_name: str,
                prefix_depth: int, top_files: int) -> BucketReport:
    try:
        bucket = client.get_bucket(bucket_name)        # one metadata GET
    except Exception as e:                              # noqa: BLE001
        return BucketReport(name=bucket_name, location="", location_type="",
                            default_storage_class="", versioning_enabled=False,
                            error=str(e))

    rep = BucketReport(
        name=bucket.name,
        location=bucket.location or "",
        location_type=(bucket.location_type or "region"),
        default_storage_class=bucket.storage_class or "STANDARD",
        versioning_enabled=bool(bucket.versioning_enabled),
        lifecycle_rules=_lifecycle_summary(list(bucket.lifecycle_rules)),
        created=bucket.time_created.strftime("%Y-%m-%d") if bucket.time_created else "",
    )

    folders: dict[str, FolderAgg] = defaultdict(lambda: FolderAgg(folder=""))
    classes: dict[str, dict] = defaultdict(lambda: {"size": 0, "count": 0, "cost": 0.0})

    # versions=True so we also see noncurrent (superseded/soft-deleted) versions.
    blobs = client.list_blobs(bucket, versions=True, fields=_BLOB_FIELDS)
    for b in blobs:
        size = int(b.size or 0)
        sc = pricing.normalise_class(b.storage_class or rep.default_storage_class)
        cost = pricing.monthly_cost(size, rep.location_type, sc)
        state = "noncurrent" if b.time_deleted else "live"
        updated = b.updated.strftime("%Y-%m-%d") if b.updated else ""

        row = ObjectRow(rep.name, b.name, _folder_of(b.name, prefix_depth),
                        size, sc, updated, state, cost)
        rep.objects.append(row)

        rep.object_count += 1
        rep.total_size += size
        rep.cost_month += cost
        if state == "live":
            rep.live_count += 1
            rep.live_size += size
        else:
            rep.noncurrent_count += 1
            rep.noncurrent_size += size

        fa = folders[row.folder]
        fa.folder = row.folder
        fa.count += 1
        fa.size += size
        fa.cost_month += cost

        c = classes[sc]
        c["size"] += size
        c["count"] += 1
        c["cost"] += cost

    rep.class_breakdown = dict(classes)
    rep.folders = sorted(folders.values(), key=lambda f: f.size, reverse=True)
    rep.top_files = sorted(rep.objects, key=lambda o: o.size, reverse=True)[:top_files]
    return rep


def scan(project: str, bucket_names: list[str] | None,
         prefix_depth: int, top_files: int, workers: int) -> list[BucketReport]:
    client = storage.Client(project=project)
    if not bucket_names:
        print(f"→ Listing buckets in project '{project}'…")
        bucket_names = [b.name for b in client.list_buckets()]
    print(f"→ Scanning {len(bucket_names)} bucket(s) with {workers} workers…\n")

    reports: list[BucketReport] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(scan_bucket, client, n, prefix_depth, top_files): n
                   for n in bucket_names}
        for fut in as_completed(futures):
            rep = fut.result()
            if rep.error:
                print(f"   ✗ {rep.name}: {rep.error}")
            else:
                print(f"   ✓ {rep.name}: {rep.object_count:,} objects, "
                      f"{format_size(rep.total_size)}, ~${rep.cost_month:,.2f}/mo")
            reports.append(rep)
    reports.sort(key=lambda r: r.total_size, reverse=True)
    return reports


def write_csv(reports: list[BucketReport], path: str) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["bucket", "object", "folder", "size_bytes", "size_human",
                    "storage_class", "state", "updated", "cost_month_usd"])
        for rep in reports:
            for o in rep.objects:
                w.writerow([o.bucket, o.name, o.folder, o.size, format_size(o.size),
                            o.storage_class, o.state, o.updated, f"{o.cost_month:.6f}"])
    print(f"→ Wrote full per-object CSV: {path}")


def main() -> int:
    p = argparse.ArgumentParser(description="Analyse GCS buckets → PDF report.")
    p.add_argument("--project", default=PROJECT_ID, required=True, help="GCP project ID")
    p.add_argument("--buckets", default="", help="comma-separated bucket names (default: all)")
    p.add_argument("--prefix-depth", type=int, default=PREFIX_DEPTH,
                   help="path segments that define a 'folder' (default 1)")
    p.add_argument("--top-files", type=int, default=TOP_FILES,
                   help="largest N files listed per bucket in the PDF")
    p.add_argument("--workers", type=int, default=WORKERS, help="parallel buckets")
    p.add_argument("--output", default="", help="PDF path (default: timestamped)")
    p.add_argument("--csv", action="store_true", help="also write full per-object CSV")
    args = p.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_pdf = args.output or f"gcs_report_{args.project}_{ts}.pdf"
    bucket_names = [b.strip() for b in args.buckets.split(",") if b.strip()] or None

    try:
        reports = scan(args.project, bucket_names, args.prefix_depth,
                       args.top_files, args.workers)
    except Exception as e:                              # noqa: BLE001
        print(f"\n✗ Scan failed: {e}\n"
              f"  Did you run `gcloud auth application-default login`?", file=sys.stderr)
        return 1

    if not any(not r.error for r in reports):
        print("\n✗ No buckets could be read. Check project / permissions.", file=sys.stderr)
        return 1

    report.build_pdf(reports, out_pdf, project=args.project,
                     prefix_depth=args.prefix_depth, format_size=format_size)
    print(f"\n✓ PDF report: {out_pdf}")

    if args.csv:
        write_csv(reports, out_pdf.rsplit(".", 1)[0] + ".csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
