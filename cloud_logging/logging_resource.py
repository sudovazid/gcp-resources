import sys
import os
import csv
import warnings

try:
    from googleapiclient import discovery
    import google.auth
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-api-python-client google-auth')
    from googleapiclient import discovery
    import google.auth

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(resource_path):
    return resource_path.split('/')[-1] if resource_path else "Unknown"

def extract_location_and_bucket(resource_path):
    # Format: projects/{project_id}/locations/{location}/buckets/{bucket_id}
    parts = resource_path.split('/')
    if len(parts) >= 6:
        return parts[3], parts[5]
    return "Unknown", extract_name(resource_path)

def audit_logging(project_id):
    print(f"\n🚀 Fetching Cloud Logging Resources for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('logging', 'v2', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Cloud Logging client: {e}")
        return

    parent = f"projects/{project_id}"
    
    # 1. SINK AUDIT
    print(f"\n[1/4] Scanning Log Sinks...")
    sinks_csv = f"{project_id}_logging_sinks_audit.csv"
    sinks_list = []
    try:
        request = client.projects().sinks().list(parent=parent)
        while request is not None:
            response = request.execute()
            sinks_list.extend(response.get('sinks', []))
            request = client.projects().sinks().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Sinks: {e}")

    print(f"\n{'Sink Name':<25} | {'Destination':<45} | {'Disabled':<8} | {'Filter'}")
    print("-" * 110)
    
    with open(sinks_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Sink Name", "Destination", "Disabled", "Filter", "Writer Identity"])
        
        for sink in sinks_list:
            name = sink.get('name', 'Unknown')
            dest = sink.get('destination', 'Unknown')
            disabled = sink.get('disabled', False)
            log_filter = sink.get('filter', 'None')
            writer_id = sink.get('writerIdentity', 'N/A')
            
            display_name = name if len(name) <= 25 else name[:22] + "..."
            display_dest = dest if len(dest) <= 45 else dest[:42] + "..."
            display_filter = log_filter if len(log_filter) <= 30 else log_filter[:27] + "..."
            
            print(f"{display_name:<25} | {display_dest:<45} | {str(disabled):<8} | {display_filter}")
            writer.writerow([name, dest, disabled, log_filter, writer_id])
    print(f"      Found {len(sinks_list)} Log Sinks. Report saved to: {sinks_csv}")

    # 2. LOG BUCKETS AUDIT
    print(f"\n[2/4] Scanning Log Buckets...")
    buckets_csv = f"{project_id}_logging_buckets_audit.csv"
    buckets_list = []
    try:
        request = client.projects().locations().buckets().list(parent=f"{parent}/locations/-")
        while request is not None:
            response = request.execute()
            buckets_list.extend(response.get('buckets', []))
            request = client.projects().locations().buckets().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Log Buckets: {e}")

    print(f"\n{'Bucket ID':<20} | {'Location':<15} | {'Retention Days':<15} | {'Locked':<8} | {'State'}")
    print("-" * 75)
    
    with open(buckets_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Bucket ID", "Location", "Retention Days", "Locked", "Lifecycle State", "Description"])
        
        for bucket in buckets_list:
            name_path = bucket.get('name', '')
            loc, bucket_id = extract_location_and_bucket(name_path)
            retention = bucket.get('retentionDays', 30)
            locked = bucket.get('locked', False)
            state = bucket.get('lifecycleState', 'Unknown')
            desc = bucket.get('description', '')
            
            print(f"{bucket_id:<20} | {loc:<15} | {str(retention):<15} | {str(locked):<8} | {state}")
            writer.writerow([bucket_id, loc, retention, locked, state, desc])
    print(f"      Found {len(buckets_list)} Log Buckets. Report saved to: {buckets_csv}")

    # 3. LOG EXCLUSIONS AUDIT
    print(f"\n[3/4] Scanning Log Exclusions...")
    exclusions_csv = f"{project_id}_logging_exclusions_audit.csv"
    exclusions_list = []
    try:
        request = client.projects().exclusions().list(parent=parent)
        while request is not None:
            response = request.execute()
            exclusions_list.extend(response.get('exclusions', []))
            request = client.projects().exclusions().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Log Exclusions: {e}")

    print(f"\n{'Exclusion Name':<25} | {'Disabled':<8} | {'Filter'}")
    print("-" * 65)
    
    with open(exclusions_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Exclusion Name", "Disabled", "Filter", "Description"])
        
        for excl in exclusions_list:
            name = excl.get('name', 'Unknown')
            disabled = excl.get('disabled', False)
            log_filter = excl.get('filter', 'None')
            desc = excl.get('description', '')
            
            display_name = name if len(name) <= 25 else name[:22] + "..."
            display_filter = log_filter if len(log_filter) <= 30 else log_filter[:27] + "..."
            
            print(f"{display_name:<25} | {str(disabled):<8} | {display_filter}")
            writer.writerow([name, disabled, log_filter, desc])
    print(f"      Found {len(exclusions_list)} Log Exclusions. Report saved to: {exclusions_csv}")

    # 4. LOG METRICS AUDIT
    print(f"\n[4/4] Scanning Log Metrics (User-defined)...")
    metrics_csv = f"{project_id}_logging_metrics_audit.csv"
    metrics_list = []
    try:
        request = client.projects().metrics().list(parent=parent)
        while request is not None:
            response = request.execute()
            metrics_list.extend(response.get('metrics', []))
            request = client.projects().metrics().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Log Metrics: {e}")

    print(f"\n{'Metric Name':<25} | {'Value Type':<15} | {'Filter'}")
    print("-" * 75)
    
    with open(metrics_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric Name", "Value Type", "Filter", "Description"])
        
        for metric in metrics_list:
            name = metric.get('name', 'Unknown')
            desc = metric.get('description', '')
            log_filter = metric.get('filter', 'None')
            
            descriptor = metric.get('metricDescriptor', {})
            val_type = descriptor.get('valueType', 'Unknown')
            
            display_name = name if len(name) <= 25 else name[:22] + "..."
            display_filter = log_filter if len(log_filter) <= 35 else log_filter[:32] + "..."
            
            print(f"{display_name:<25} | {val_type:<15} | {display_filter}")
            writer.writerow([name, val_type, log_filter, desc])
    print(f"      Found {len(metrics_list)} Log Metrics. Report saved to: {metrics_csv}")

    print(f"\n✅ Cloud Logging Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_logging(project_input)
