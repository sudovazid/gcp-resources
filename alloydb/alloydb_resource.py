import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import alloydb_v1
    from google.api_core import exceptions
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-alloydb')
    from google.cloud import alloydb_v1
    from google.api_core import exceptions

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_alloydb(project_id):
    print(f"\nFetching AlloyDB Resources for project: {project_id}...")
    client = alloydb_v1.AlloyDBAdminClient()

    # AlloyDB clusters
    cl_csv = f"{project_id}_alloydb_clusters_audit.csv"
    cluster_list = []
    locations = ["-"]
    try:
        parent = f"projects/{project_id}/locations/-"
        clusters = list(client.list_clusters(parent=parent))
    except Exception as e:
        print(f"  Error listing clusters: {e}")
        clusters = []

    with open(cl_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Cluster Name", "Display Name", "Location", "Network", "State", "Database Version", "Primary / Secondary", "Backup Source", "Continuous Backup Retention (d)", "Continuous Backup Enabled"])
        for cl in clusters:
            cluster_list.append(cl)
            cb = cl.continuous_backup_config if hasattr(cl, "continuous_backup_config") else None
            writer.writerow([
                cl.name.split("/")[-1],
                cl.display_name,
                cl.name.split("/")[-3] if "/locations/" in cl.name else "",
                getattr(cl, "network", ""),
                cl.state.name if hasattr(cl.state, "name") else str(cl.state),
                getattr(cl, "database_version", ""),
                "Primary" if not hasattr(cl, "cluster_type") or not cl.cluster_type else str(cl.cluster_type),
                getattr(cl, "backup_source", ""),
                cb.retention_count if cb else "",
                cb.enabled if cb else "",
            ])
            print(f"  Cluster: {cl.name.split('/')[-1]}, Location: {cl.name.split('/')[-3] if '/locations/' in cl.name else ''}")
    print(f"  Found {len(cluster_list)} clusters. Report saved to: {cl_csv}")

    # Instances (primary + read pool)
    inst_csv = f"{project_id}_alloydb_instances_audit.csv"
    inst_count = 0
    with open(inst_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Cluster Name", "Instance ID", "Instance Type", "State", "Machine CPU Count", "Availability Type", "Public IP", "Outbound Public IP", "Create Time"])
        for cl in cluster_list:
            try:
                instances = list(client.list_instances(parent=cl.name))
                for inst in instances:
                    inst_count += 1
                    machine = inst.machine_config if hasattr(inst, "machine_config") else None
                    writer.writerow([
                        cl.name.split("/")[-1],
                        inst.name.split("/")[-1],
                        inst.instance_type.name if hasattr(inst.instance_type, "name") else str(inst.instance_type),
                        inst.state.name if hasattr(inst.state, "name") else str(inst.state),
                        machine.cpu_count if machine else "",
                        inst.availability_type.name if hasattr(inst.availability_type, "name") else "",
                        inst.public_ip_address if hasattr(inst, "public_ip_address") else "",
                        inst.outbound_public_ip_addresses if hasattr(inst, "outbound_public_ip_addresses") and inst.outbound_public_ip_addresses else "",
                        inst.create_time.strftime("%Y-%m-%d %H:%M:%S") if inst.create_time else "",
                    ])
            except Exception:
                pass
    print(f"  Found {inst_count} instances. Report saved to: {inst_csv}")

    # Backups
    bk_csv = f"{project_id}_alloydb_backups_audit.csv"
    bk_count = 0
    with open(bk_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Backup Name", "Display Name", "Cluster", "State", "Type", "Size (GiB)", "Create Time", "Expiry Time"])
        try:
            parent = f"projects/{project_id}/locations/-"
            backups = list(client.list_backups(parent=parent))
            for bk in backups:
                bk_count += 1
                writer.writerow([
                    bk.name.split("/")[-1],
                    bk.display_name,
                    bk.cluster_name.split("/")[-1] if bk.cluster_name else "",
                    bk.state.name if hasattr(bk.state, "name") else str(bk.state),
                    bk.type_.name if hasattr(bk, "type_") and hasattr(bk.type_, "name") else "",
                    f"{bk.size_bytes / (1024**3):.2f}" if bk.size_bytes else "0",
                    bk.create_time.strftime("%Y-%m-%d %H:%M:%S") if bk.create_time else "",
                    bk.expiry_time.strftime("%Y-%m-%d %H:%M:%S") if bk.expiry_time else "",
                ])
        except Exception:
            pass
    print(f"  Found {bk_count} backups. Report saved to: {bk_csv}")
    print("AlloyDB Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_alloydb(project_input)
