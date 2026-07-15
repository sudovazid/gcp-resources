import os
import sys
import warnings
import time
import csv
from google.cloud import monitoring_v3
from google.cloud import storage

# 1. Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def get_comprehensive_bucket_report(project_id):
    print(f"\n1. Fetching instant sizes from Monitoring...")
    monitoring_client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"
    
    # Get sizes from the last 24 hours
    now = time.time()
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(now)},
        "start_time": {"seconds": int(now) - 86400},
    })

    bucket_sizes = {}
    try:
        results = monitoring_client.list_time_series(
            request={
                "name": project_name,
                "filter": 'metric.type = "storage.googleapis.com/storage/total_bytes"',
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )
        for result in results:
            if result.points:
                b_name = result.resource.labels.get('bucket_name')
                latest_bytes = result.points[0].value.double_value
                size_in_gb = latest_bytes / (1024**3)
                
                # FIX: Add the sizes together if the bucket has multiple storage classes!
                if b_name in bucket_sizes:
                    bucket_sizes[b_name] += size_in_gb
                else:
                    bucket_sizes[b_name] = size_in_gb
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch bucket sizes from Monitoring API ({e}). Bucket sizes will default to 0.00 GB.")

    print(f"2. Fetching bucket metadata from Storage API...\n")
    try:
        storage_client = storage.Client(project=project_id)
        buckets = list(storage_client.list_buckets())
    except Exception as e:
        err_str = str(e)
        print(f"❌ Error listing GCS buckets: {err_str}")
        if "403" in err_str or "permission" in err_str.lower() or "denied" in err_str.lower():
            print(f"   💡 Recommendation: The authenticated identity lacks permission to list GCS buckets.")
            print(f"      Please ensure you have the 'Storage Viewer' (roles/storage.viewer) or 'Viewer' (roles/viewer) IAM role")
            print(f"      assigned on project '{project_id}'.")
        return

    # Setup the console table header
    print(f"{'Bucket Name':<42} | {'Size (GB)':<9} | {'Location':<11} | {'Class':<8} | {'Version':<7} | {'Encryption':<14} | {'Public Access'}")
    print("-" * 123)

    # Open the CSV file to write at the same time
    csv_filename = f"{project_id}_gcs_resources.csv"
    with open(csv_filename, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        # Write CSV Header
        writer.writerow(["Bucket Name", "Size (GB)", "Location", "Class", "Version", "Encryption", "Public Access"])

        for bucket in buckets:
            name = bucket.name
            display_name = name if len(name) <= 42 else name[:39] + "..."
            
            size_gb = bucket_sizes.get(name, 0.0)
            location = bucket.location
            storage_class = bucket.storage_class
            versioning = "Yes" if bucket.versioning_enabled else "No"
            encryption = "CMEK" if bucket.default_kms_key_name else "Google-Managed"
            
            # Check Public Access
            pap = bucket.iam_configuration.public_access_prevention
            if pap == "enforced":
                public_status = "Prevented"
            else:
                try:
                    policy = bucket.get_iam_policy(requested_policy_version=3)
                    is_public = any('allUsers' in b['members'] or 'allAuthenticatedUsers' in b['members'] for b in policy.bindings)
                    public_status = "Public!" if is_public else "Not Public"
                except Exception:
                    public_status = "Unknown (No Perms)"

            # 1. Print to Terminal
            print(f"{display_name:<42} | {size_gb:>6.2f} GB | {location:<11} | {storage_class:<8} | {versioning:<7} | {encryption:<14} | {public_status}")
            
            # 2. Write to CSV
            writer.writerow([name, f"{size_gb:.2f}", location, storage_class, versioning, encryption, public_status])

    print(f"\n✅ Success! Data printed above and cleanly exported to: {csv_filename}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_input = sys.argv[1]
    else:
        project_input = input("Enter your GCP project ID: ").strip()

    if project_input:
        get_comprehensive_bucket_report(project_input)
    else:
        print("Project ID cannot be empty.")
        sys.exit(1)