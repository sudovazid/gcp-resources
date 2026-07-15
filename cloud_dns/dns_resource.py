import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import dns
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-dns')
    from google.cloud import dns

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_dns(project_id):
    print(f"\nFetching Cloud DNS Resources for project: {project_id}...")
    client = dns.Client(project=project_id)

    # Managed zones
    zone_csv = f"{project_id}_dns_zones_audit.csv"
    zones = list(client.list_zones())
    with open(zone_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Zone Name", "DNS Name", "Description", "Visibility", "Private Visibility Config", "DNSSEC State", "DNSSEC Key Spec", "Name Servers", "Create Time"])
        for zone in zones:
            zone.reload()
            dnssec = zone.dnssec_config or {}
            writer.writerow([
                zone.name,
                zone.dns_name,
                zone.description,
                "Private" if zone.private else "Public",
                zone.networks if zone.private else "",
                dnssec.get("state", ""),
                dnssec.get("defaultKeySpecs", ""),
                ", ".join(zone.name_servers) if zone.name_servers else "",
                zone.created.strftime("%Y-%m-%d %H:%M:%S") if zone.created else "",
            ])
            print(f"  Zone: {zone.name}, DNS: {zone.dns_name}, Visibility: {'Private' if zone.private else 'Public'}")
    print(f"  Found {len(zones)} managed zones. Report saved to: {zone_csv}")

    # Record sets per zone
    rec_csv = f"{project_id}_dns_records_audit.csv"
    rec_count = 0
    with open(rec_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Zone Name", "Record Name", "Record Type", "TTL (s)", "Routing Policy", "Rrdatas"])
        for zone in zones:
            try:
                records = list(zone.list_resource_record_sets())
                for rec in records:
                    rec_count += 1
                    routing = ""
                    if hasattr(rec, "routing_policy") and rec.routing_policy:
                        routing = str(rec.routing_policy)
                    writer.writerow([
                        zone.name,
                        rec.name,
                        rec.record_type,
                        rec.ttl,
                        routing,
                        ", ".join(rec.rrdatas) if rec.rrdatas else "",
                    ])
            except Exception:
                pass
    print(f"  Found {rec_count} record sets. Report saved to: {rec_csv}")
    print("Cloud DNS Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_dns(project_input)
