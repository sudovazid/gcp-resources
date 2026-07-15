import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import bigquery
except ImportError:
    print("Missing required library. Run: pip install google-cloud-bigquery")
    sys.exit(1)

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def format_expiration_ms(ms):
    if not ms:
        return "None"
    seconds = ms // 1000
    days = seconds // 86400
    if days > 0:
        return f"{days} days"
    hours = seconds // 3600
    return f"{hours} hours"

def audit_bigquery(project_id):
    print(f"\nFetching BigQuery Resources for project: {project_id}...")
    client = bigquery.Client(project=project_id)

    # [1/4] DATASETS AUDIT
    ds_csv = f"{project_id}_bigquery_datasets_audit.csv"
    ds_count = 0
    ds_refs = []
    try:
        datasets = list(client.list_datasets())
    except Exception as e:
        print(f"  Error fetching datasets: {e}")
        datasets = []
    with open(ds_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Dataset Name", "Location", "Default Table Expiration", "Default Partition Expiration", "Default KMS Key (CMEK)", "Description", "Labels"])
        for item in datasets:
            ds_count += 1
            ds_refs.append(item.reference)
            try:
                ds = client.get_dataset(item.reference)
                kms = "Google-Managed"
                if ds.default_encryption_configuration:
                    kms = ds.default_encryption_configuration.kms_key_name or "Google-Managed"
                writer.writerow([
                    ds.dataset_id,
                    ds.location or "",
                    format_expiration_ms(ds.default_table_expiration_ms),
                    format_expiration_ms(ds.default_partition_expiration_ms) if hasattr(ds, "default_partition_expiration_ms") else "",
                    kms,
                    ds.description or "",
                    str(dict(ds.labels)) if ds.labels else "",
                ])
                print(f"  Dataset: {ds.dataset_id}, Location: {ds.location}")
            except Exception:
                pass
    print(f"  Found {ds_count} datasets. Report saved to: {ds_csv}")

    # [2/4] TABLES AUDIT (with partitions, clustering)
    t_csv = f"{project_id}_bigquery_tables_audit.csv"
    t_count = 0
    with open(t_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Table Name", "Dataset ID", "Table Type", "Size (MB)", "Row Count", "KMS Key (CMEK)", "Expiration Time", "Partition Field", "Partition Type", "Clustering Fields", "Require Partition Filter", "Description", "Labels"])
        for ref in ds_refs:
            try:
                tables = list(client.list_tables(ref))
            except Exception:
                continue
            for item in tables:
                t_count += 1
                try:
                    t = client.get_table(item.reference)
                    kms = "Google-Managed"
                    if t.encryption_configuration:
                        kms = t.encryption_configuration.kms_key_name or "Google-Managed"
                    pf = t.range_partitioning.field if t.range_partitioning else (t.time_partitioning.field if t.time_partitioning else "")
                    pt = ""
                    if t.time_partitioning:
                        pt = t.time_partitioning.type_.name if hasattr(t.time_partitioning.type_, "name") else str(t.time_partitioning.type_)
                    cf = ", ".join(t.clustering_fields) if t.clustering_fields else ""
                    rpf = t.require_partition_filter if hasattr(t, "require_partition_filter") else ""
                    writer.writerow([
                        t.table_id,
                        ref.dataset_id,
                        t.table_type or "",
                        f"{t.num_bytes / (1024*1024):.2f}" if t.num_bytes else "0",
                        t.num_rows or 0,
                        kms,
                        t.expires.strftime("%Y-%m-%d %H:%M:%S") if t.expires else "",
                        pf,
                        pt,
                        cf,
                        rpf,
                        t.description or "",
                        str(dict(t.labels)) if t.labels else "",
                    ])
                except Exception:
                    pass
    print(f"  Found {t_count} tables. Report saved to: {t_csv}")

    # [3/4] ROUTINES (stored procedures, UDFs)
    r_csv = f"{project_id}_bigquery_routines_audit.csv"
    r_count = 0
    with open(r_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Routine Name", "Dataset ID", "Type", "Language", "Return Type", "Body", "Create Time"])
        for ref in ds_refs:
            try:
                routines = list(client.list_routines(ref))
                for r in routines:
                    r_count += 1
                    writer.writerow([
                        r.routine_id,
                        ref.dataset_id,
                        r.type_.name if hasattr(r.type_, "name") else str(r.type_),
                        r.language or "",
                        r.return_type or "",
                        r.body[:200] if r.body else "",
                        r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else "",
                    ])
            except Exception:
                pass
    print(f"  Found {r_count} routines. Report saved to: {r_csv}")

    # [4/4] JOBS (recent)
    j_csv = f"{project_id}_bigquery_jobs_audit.csv"
    j_count = 0
    with open(j_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job ID", "Job Type", "State", "Statement Type", "User Email", "Bytes Processed", "Bytes Billed", "Billing Tier", "Start Time", "End Time", "Destination Table", "Priority"])
        try:
            jobs = list(client.list_jobs(project=project_id, max_results=100, all_users=True))
            for j in jobs:
                j_count += 1
                stmt = ""
                if hasattr(j, "statement_type") and j.statement_type:
                    stmt = j.statement_type.name if hasattr(j.statement_type, "name") else str(j.statement_type)
                dst = ""
                if j.destination:
                    dst = f"{j.destination.project}.{j.destination.dataset_id}.{j.destination.table_id}"
                writer.writerow([
                    j.job_id,
                    j.job_type,
                    j.state,
                    stmt,
                    j.user_email or "",
                    j.total_bytes_processed or 0,
                    j.total_bytes_billed or 0,
                    j.billing_tier or 0,
                    j.started.strftime("%Y-%m-%d %H:%M:%S") if j.started else "",
                    j.ended.strftime("%Y-%m-%d %H:%M:%S") if j.ended else "",
                    dst,
                    j.priority or "",
                ])
        except Exception:
            pass
    print(f"  Found {j_count} recent jobs. Report saved to: {j_csv}")
    print("BigQuery Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]
    audit_bigquery(project_input)
