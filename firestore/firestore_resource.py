import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import firestore
    from google.api_core import exceptions
except ImportError:
    print("Missing required library. Run: pip install google-cloud-firestore")
    sys.exit(1)

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_firestore(project_id):
    print(f"\nFetching Firestore Resources for project: {project_id}...")
    client = firestore.Client(project=project_id)

    # Databases
    db_csv = f"{project_id}_firestore_databases_audit.csv"
    db_list = []
    try:
        databases = client.list_databases().databases
    except AttributeError:
        databases = []
    with open(db_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Database Name", "Location", "Type", "Concurrency Mode", "App Engine Integration", "Delete Protection"])
        for db in databases:
            db_list.append(db)
            writer.writerow([
                db.name.split("/")[-1],
                db.location_id,
                db.type_.name if hasattr(db, "type_") else "",
                db.concurrency_mode.name if hasattr(db, "concurrency_mode") else "",
                getattr(db, "app_engine_integration_mode", ""),
                getattr(db, "delete_protection_state", ""),
            ])
            print(f"  Database: {db.name.split('/')[-1]}, Location: {db.location_id}")
    print(f"  Found {len(db_list)} databases. Report saved to: {db_csv}")

    # Collection groups / indexes
    idx_csv = f"{project_id}_firestore_indexes_audit.csv"
    idx_count = 0
    with open(idx_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Database", "Collection Group", "Query Scope", "Field Path", "Field Order", "Field Array Config"])
        for db_ref in db_list:
            db_name = db_ref.name.split("/")[-1]
            db_obj = client.collection_group("__dummy__")
            try:
                indexes = list(client.list_field_indexes(parent=f"{db_ref.name}/collectionGroups/-"))
                for idx in indexes:
                    idx_count += 1
                    for field in idx.fields:
                        writer.writerow([
                            db_name,
                            idx.collection_group,
                            idx.query_scope.name if hasattr(idx, "query_scope") else "",
                            field.field_path,
                            field.order.name if hasattr(field, "order") else "",
                            field.array_config.name if hasattr(field, "array_config") else "",
                        ])
            except Exception:
                pass
    print(f"  Found {idx_count} field indexes. Report saved to: {idx_csv}")
    print("Firestore Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_firestore(project_input)
