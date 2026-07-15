import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import spanner
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-spanner')
    from google.cloud import spanner

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_spanner(project_id):
    print(f"\nFetching Cloud Spanner Resources for project: {project_id}...")
    client = spanner.Client(project=project_id)

    # Instances
    inst_csv = f"{project_id}_spanner_instances_audit.csv"
    instances = list(client.list_instances())
    with open(inst_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Instance ID", "Display Name", "Configuration", "Node Count", "Processing Units", "State", "Create Time", "Update Time"])
        for inst in instances:
            inst.reload()
            writer.writerow([
                inst.instance_id,
                inst.display_name,
                inst.configuration_name,
                inst.node_count,
                getattr(inst, "processing_units", ""),
                inst.state.name if inst.state else "",
                inst.create_time.strftime("%Y-%m-%d %H:%M:%S") if inst.create_time else "",
                inst.update_time.strftime("%Y-%m-%d %H:%M:%S") if inst.update_time else "",
            ])
            print(f"  Instance: {inst.instance_id}, Nodes: {inst.node_count}, Config: {inst.configuration_name}")
    print(f"  Found {len(instances)} instances. Report saved to: {inst_csv}")

    # Databases per instance
    db_csv = f"{project_id}_spanner_databases_audit.csv"
    db_count = 0
    with open(db_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Instance ID", "Database ID", "State", "Create Time", "Version Retention", "Earliest Version Time", "Encryption Type", "KMS Key"])
        for inst in instances:
            databases = list(inst.list_databases())
            for db in databases:
                db_count += 1
                enc_info = db.encryption_config if hasattr(db, "encryption_config") and db.encryption_config else None
                writer.writerow([
                    inst.instance_id,
                    db.database_id,
                    db.state.name if db.state else "",
                    db.create_time.strftime("%Y-%m-%d %H:%M:%S") if db.create_time else "",
                    getattr(db, "version_retention_period", ""),
                    db.earliest_version_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(db, "earliest_version_time") and db.earliest_version_time else "",
                    enc_info.encryption_type.name if enc_info else "",
                    enc_info.kms_key_name if enc_info and hasattr(enc_info, "kms_key_name") else "",
                ])
            if databases:
                print(f"  Instance {inst.instance_id}: {len(databases)} databases")
    print(f"  Found {db_count} databases. Report saved to: {db_csv}")

    # Backup info
    bk_csv = f"{project_id}_spanner_backups_audit.csv"
    bk_count = 0
    with open(bk_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Instance ID", "Backup ID", "Database", "State", "Create Time", "Expire Time", "Size (GiB)"])
        for inst in instances:
            try:
                backups = list(inst.list_backups())
                for bk in backups:
                    bk_count += 1
                    writer.writerow([
                        inst.instance_id,
                        bk.backup_id,
                        bk.database,
                        bk.state.name if bk.state else "",
                        bk.create_time.strftime("%Y-%m-%d %H:%M:%S") if bk.create_time else "",
                        bk.expire_time.strftime("%Y-%m-%d %H:%M:%S") if bk.expire_time else "",
                        f"{bk.size_bytes / (1024**3):.2f}" if bk.size_bytes else "0",
                    ])
            except Exception:
                pass
    print(f"  Found {bk_count} backups. Report saved to: {bk_csv}")
    print("Cloud Spanner Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_spanner(project_input)
