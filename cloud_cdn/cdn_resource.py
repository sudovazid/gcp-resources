import sys
import os
import csv
import warnings

try:
    from google.cloud import compute_v1
except ImportError:
    print("❌ Error: Missing required library. Please run: pip install google-cloud-compute")
    sys.exit(1)

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_cdn(project_id):
    print(f"\n🚀 Fetching Cloud CDN Resources for project: {project_id}...")
    
    # Initialize Clients
    try:
        services_client = compute_v1.BackendServicesClient()
        buckets_client = compute_v1.BackendBucketsClient()
    except Exception as e:
        print(f"❌ Error initializing Compute clients: {e}")
        return

    # 1. AUDIT BACKEND SERVICES
    print(f"\n[1/2] Scanning Backend Services for Cloud CDN...")
    services_csv = f"{project_id}_cdn_backend_services_audit.csv"
    services_list = []
    try:
        response = services_client.list(project=project_id)
        services_list = list(response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Backend Services: {e}")

    print(f"\n{'Backend Service Name':<35} | {'Protocol':<10} | {'CDN Enabled':<12} | {'Cache Mode':<15} | {'Default TTL'}")
    print("-" * 90)

    with open(services_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Backend Service Name", "Protocol", "CDN Enabled", "Cache Mode", "Default TTL"])

        for svc in services_list:
            name = svc.name
            protocol = svc.protocol
            cdn_enabled = getattr(svc, "enable_c_d_n", False)
            
            cache_mode = "N/A"
            default_ttl = "N/A"
            if cdn_enabled and svc.cdn_policy:
                raw_mode = svc.cdn_policy.cache_mode
                cache_mode = str(raw_mode) if raw_mode else "Unknown"
                default_ttl = f"{svc.cdn_policy.default_ttl}s" if svc.cdn_policy.default_ttl is not None else "Default"
            
            display_name = name if len(name) <= 35 else name[:32] + "..."
            print(f"{display_name:<35} | {protocol:<10} | {str(cdn_enabled):<12} | {cache_mode:<15} | {default_ttl}")
            writer.writerow([name, protocol, cdn_enabled, cache_mode, default_ttl])

    print(f"      Found {len(services_list)} Backend Services. Report saved to: {services_csv}")

    # 2. AUDIT BACKEND BUCKETS
    print(f"\n[2/2] Scanning Backend Buckets for Cloud CDN...")
    buckets_csv = f"{project_id}_cdn_backend_buckets_audit.csv"
    buckets_list = []
    try:
        response = buckets_client.list(project=project_id)
        buckets_list = list(response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Backend Buckets: {e}")

    print(f"\n{'Backend Bucket Name':<35} | {'GCS Bucket Name':<20} | {'CDN Enabled':<12} | {'Cache Mode':<15} | {'Default TTL'}")
    print("-" * 100)

    with open(buckets_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Backend Bucket Name", "GCS Bucket Name", "CDN Enabled", "Cache Mode", "Default TTL"])

        for bucket in buckets_list:
            name = bucket.name
            gcs_bucket = bucket.bucket_name
            cdn_enabled = getattr(bucket, "enable_cdn", False)
            
            cache_mode = "N/A"
            default_ttl = "N/A"
            if cdn_enabled and bucket.cdn_policy:
                raw_mode = bucket.cdn_policy.cache_mode
                cache_mode = str(raw_mode) if raw_mode else "Unknown"
                default_ttl = f"{bucket.cdn_policy.default_ttl}s" if bucket.cdn_policy.default_ttl is not None else "Default"
                
            display_name = name if len(name) <= 35 else name[:32] + "..."
            display_gcs = gcs_bucket if len(gcs_bucket) <= 20 else gcs_bucket[:17] + "..."
            print(f"{display_name:<35} | {display_gcs:<20} | {str(cdn_enabled):<12} | {cache_mode:<15} | {default_ttl}")
            writer.writerow([name, gcs_bucket, cdn_enabled, cache_mode, default_ttl])

    print(f"      Found {len(buckets_list)} Backend Buckets. Report saved to: {buckets_csv}")
    print(f"\n✅ Cloud CDN Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_cdn(project_input)
