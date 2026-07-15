import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import eventarc_v1
    from google.api_core import exceptions
except ImportError:
    print("Missing required library. Run: pip install google-cloud-eventarc")
    sys.exit(1)

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_eventarc(project_id):
    print(f"\nFetching Eventarc Resources for project: {project_id}...")
    client = eventarc_v1.EventarcClient()

    # Triggers
    trig_csv = f"{project_id}_eventarc_triggers_audit.csv"
    trig_count = 0
    with open(trig_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Trigger Name", "Location", "Event Filters", "Destination Type", "Destination URI", "Service Account", "Transport Type", "Channel", "Create Time", "Update Time", "Labels"])
        try:
            parent = f"projects/{project_id}/locations/-"
            triggers = list(client.list_triggers(parent=parent))
            for trig in triggers:
                trig_count += 1
                loc = trig.name.split("/")[-3] if "/locations/" in trig.name else ""
                filters = "; ".join([f"{ef.attribute}={ef.value}" for ef in trig.event_filters]) if trig.event_filters else ""
                dest_type = ""
                dest_uri = ""
                if trig.destination.cloud_run:
                    dest_type = "Cloud Run"
                    dest_uri = trig.destination.cloud_run.service
                elif trig.destination.gke:
                    dest_type = "GKE"
                    dest_uri = trig.destination.gke.service
                elif trig.destination.workflow:
                    dest_type = "Workflows"
                    dest_uri = trig.destination.workflow
                transport = trig.transport.pubsub.topic if trig.transport and trig.transport.pubsub else ""
                writer.writerow([
                    trig.name.split("/")[-1],
                    loc,
                    filters,
                    dest_type,
                    dest_uri,
                    trig.service_account,
                    "Pub/Sub" if transport else "Direct",
                    transport,
                    trig.create_time.strftime("%Y-%m-%d %H:%M:%S") if trig.create_time else "",
                    trig.update_time.strftime("%Y-%m-%d %H:%M:%S") if trig.update_time else "",
                    str(dict(trig.labels)) if trig.labels else "",
                ])
                print(f"  Trigger: {trig.name.split('/')[-1]}, Location: {loc}, Dest: {dest_type}")
        except Exception as e:
            print(f"  Error listing triggers: {e}")
    print(f"  Found {trig_count} triggers. Report saved to: {trig_csv}")

    # Channels
    ch_csv = f"{project_id}_eventarc_channels_audit.csv"
    ch_count = 0
    with open(ch_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Channel Name", "Location", "State", "Provider", "Target", "Create Time", "Update Time"])
        try:
            parent = f"projects/{project_id}/locations/-"
            channels = list(client.list_channels(parent=parent))
            for ch in channels:
                ch_count += 1
                loc = ch.name.split("/")[-3] if "/locations/" in ch.name else ""
                writer.writerow([
                    ch.name.split("/")[-1],
                    loc,
                    ch.state.name if hasattr(ch.state, "name") else str(ch.state),
                    ch.provider,
                    ch.pubsub_topic or "",
                    ch.create_time.strftime("%Y-%m-%d %H:%M:%S") if ch.create_time else "",
                    ch.update_time.strftime("%Y-%m-%d %H:%M:%S") if ch.update_time else "",
                ])
                print(f"  Channel: {ch.name.split('/')[-1]}, Location: {loc}")
        except Exception:
            pass
    print(f"  Found {ch_count} channels. Report saved to: {ch_csv}")
    print("Eventarc Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_eventarc(project_input)
