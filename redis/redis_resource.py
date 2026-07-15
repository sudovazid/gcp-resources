import csv
import os
import sys
import warnings

try:
    from google.cloud import redis_v1
except ImportError:
    print("❌ Error: Missing required library. Please run: pip install google-cloud-redis")
    sys.exit(1)

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_redis(project_id):
    print(f"Fetching Cloud Memorystore (Redis) Instances for project: {project_id}...")

    client = redis_v1.CloudRedisClient()
    # Using '-' searches across all regions globally
    parent = f"projects/{project_id}/locations/-"

    try:
        request = redis_v1.ListInstancesRequest(parent=parent)
        instances = client.list_instances(request=request)
    except Exception as e:
        err_str = str(e)
        print(f"❌ Error fetching Redis instances: {err_str}")
        if "api has not been used" in err_str.lower() or "disabled" in err_str.lower() or "service_disabled" in err_str.lower():
            print(f"   💡 Recommendation: The 'Google Cloud Memorystore for Redis API' is currently disabled in project '{project_id}'.")
            print(f"      Please enable it by running: gcloud services enable redis.googleapis.com --project {project_id}")
            print(f"      Or visit: https://console.developers.google.com/apis/api/redis.googleapis.com/overview?project={project_id}")
        elif "permission" in err_str.lower() or "403" in err_str or "unauthorized" in err_str.lower():
            print(f"   💡 Recommendation: The authenticated identity lacks permission to list Redis instances.")
            print(f"      Please ensure you have the 'Cloud Memorystore Redis Viewer' (roles/redis.viewer) or 'Viewer' (roles/viewer) IAM role.")
        instances = []

    print(f"\n{'Instance Name':<30} | {'Location':<15} | {'Tier':<12} | {'Cap (GB)':<9} | {'Version':<12} | {'State'}")
    print("-" * 95)

    csv_file = f"{project_id}_redis_audit.csv"
    count = 0

    with open(csv_file, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Instance Name", "Location", "Tier", "Capacity (GB)", "Redis Version", "State", "Host IP", "Port"])

        for instance in instances:
            count += 1
            
            # Extract name from the full resource path
            name = instance.name.split('/')[-1]
            display_name = name if len(name) <= 30 else name[:27] + "..."
            
            location = instance.location_id
            
            # Clean up tier name (e.g., Tier.BASIC -> BASIC)
            tier = instance.tier.name if hasattr(instance.tier, 'name') else str(instance.tier)
            tier = tier.replace('Tier.', '').replace('TIER_', '')
            
            capacity = instance.memory_size_gb
            
            # Format version string
            version = instance.redis_version
            if version.startswith("REDIS_"):
                version = version.replace("REDIS_", "Redis ")
                
            state = instance.state.name if hasattr(instance.state, 'name') else str(instance.state)
            state = state.replace('State.', '')
            
            host = instance.host
            port = instance.port

            print(f"{display_name:<30} | {location:<15} | {tier:<12} | {capacity:<9} | {version:<12} | {state}")
            writer.writerow([name, location, tier, capacity, version, state, host, port])

    if count == 0:
        print("No Cloud Memorystore (Redis) instances found in this project.")
        
    print(f"\n✅ Redis Audit complete. {count} instances saved to {csv_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Project ID argument missing.")
        sys.exit(1)

    project_id_arg = sys.argv[1]
    audit_redis(project_id_arg)
