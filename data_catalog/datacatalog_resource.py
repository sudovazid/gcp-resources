import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import datacatalog_v1
    from google.api_core import exceptions
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-datacatalog')
    from google.cloud import datacatalog_v1
    from google.api_core import exceptions

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_datacatalog(project_id):
    print(f"\nFetching Data Catalog Resources for project: {project_id}...")
    client = datacatalog_v1.DataCatalogClient()

    # Tag templates
    tt_csv = f"{project_id}_datacatalog_tag_templates_audit.csv"
    tt_count = 0
    with open(tt_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Tag Template Name", "Location", "Display Name", "Fields", "Is Publicly Readable"])
        try:
            parent = f"projects/{project_id}/locations/-"
            templates = list(client.list_tag_templates(parent=parent))
            for tt in templates:
                tt_count += 1
                loc = tt.name.split("/locations/")[1].split("/")[0] if "/locations/" in tt.name else ""
                fields = "; ".join([f"{fn}({fv.type_.primitive_type.name if fv.type_ and fv.type_.primitive_type else '?'})" for fn, fv in tt.fields.items()]) if tt.fields else ""
                writer.writerow([
                    tt.name.split("/")[-1],
                    loc,
                    tt.display_name,
                    fields,
                    tt.is_publicly_readable,
                ])
                print(f"  Tag Template: {tt.name.split('/')[-1]}, Location: {loc}")
        except Exception as e:
            print(f"  Error listing tag templates: {e}")
    print(f"  Found {tt_count} tag templates. Report saved to: {tt_csv}")

    # Entry groups
    eg_csv = f"{project_id}_datacatalog_entry_groups_audit.csv"
    eg_count = 0
    with open(eg_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Entry Group Name", "Location", "Display Name", "Description", "Entry Count"])
        try:
            parent = f"projects/{project_id}/locations/-"
            groups = list(client.list_entry_groups(parent=parent))
            for eg in groups:
                eg_count += 1
                loc = eg.name.split("/locations/")[1].split("/")[0] if "/locations/" in eg.name else ""
                writer.writerow([
                    eg.name.split("/")[-1],
                    loc,
                    eg.display_name,
                    eg.description,
                ])
                print(f"  Entry Group: {eg.name.split('/')[-1]}, Location: {loc}")
        except Exception as e:
            print(f"  Error listing entry groups: {e}")
    print(f"  Found {eg_count} entry groups. Report saved to: {eg_csv}")

    # Entries per group
    ent_csv = f"{project_id}_datacatalog_entries_audit.csv"
    ent_count = 0
    with open(ent_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Entry Name", "Entry Group", "Location", "Type", "User Specified Type", "Display Name", "Description", "Linked Resource", "Schema Columns"])
        try:
            parent = f"projects/{project_id}/locations/-"
            groups = list(client.list_entry_groups(parent=parent))
            for eg in groups:
                try:
                    entries = list(client.list_entries(parent=eg.name))
                    for e in entries:
                        ent_count += 1
                        loc = e.name.split("/locations/")[1].split("/")[0] if "/locations/" in e.name else ""
                        cols = "; ".join([f"{c.column}({c.type_})" for c in e.schema.columns]) if e.schema and e.schema.columns else ""
                        writer.writerow([
                            e.name.split("/")[-1],
                            eg.name.split("/")[-1],
                            loc,
                            e.type_.name if hasattr(e, "type_") and hasattr(e.type_, "name") else "",
                            e.user_specified_type,
                            e.display_name,
                            e.description,
                            e.linked_resource,
                            cols,
                        ])
                except Exception:
                    pass
        except Exception:
            pass
    print(f"  Found {ent_count} entries. Report saved to: {ent_csv}")
    print("Data Catalog Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_datacatalog(project_input)
