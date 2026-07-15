import sys
import os
import csv
import warnings

try:
    from googleapiclient import discovery
    import google.auth
except ImportError:
    print("❌ Error: Missing required libraries. Please run: pip install google-api-python-client google-auth")
    sys.exit(1)

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_location_and_env(resource_path):
    # Format: projects/{project_id}/locations/{location}/environments/{env_name}
    parts = resource_path.split('/')
    if len(parts) >= 6:
        return parts[3], parts[5]
    return "Unknown", resource_path.split('/')[-1] if resource_path else "Unknown"

def audit_composer(project_id):
    print(f"\n🚀 Fetching Cloud Composer (Managed Airflow) Resources for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('composer', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Cloud Composer client: {e}")
        return

    parent = f"projects/{project_id}/locations/-"
    composer_csv = f"{project_id}_composer_environments_audit.csv"
    env_list = []

    print(f"\n[1/1] Scanning Composer Environments...")
    try:
        request = client.projects().locations().environments().list(parent=parent)
        while request is not None:
            response = request.execute()
            env_list.extend(response.get('environments', []))
            request = client.projects().locations().environments().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Composer Environments: {e}")

    print(f"\n{'Environment ID':<25} | {'Location':<12} | {'State':<8} | {'Scale/Size':<10} | {'Image Version'}")
    print("-" * 90)

    with open(composer_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Environment ID", "Location", "State", "Scale/Size", "Image Version", "GKE Cluster", "DAGs GCS Prefix"])

        for env in env_list:
            name_path = env.get('name', '')
            loc, env_id = extract_location_and_env(name_path)
            state = env.get('state', 'Unknown')
            
            config = env.get('config', {})
            software_config = config.get('softwareConfig', {})
            image_version = software_config.get('imageVersion', 'Unknown')
            gke_cluster = config.get('gkeCluster', 'N/A')
            dag_bucket = config.get('dagGcsPrefix', 'N/A')
            
            node_count = config.get('nodeCount', 0)
            env_size = config.get('environmentSize', '')
            if env_size:
                scale = env_size.replace('ENVIRONMENT_SIZE_', '')
            elif node_count:
                scale = f"{node_count} nodes"
            else:
                scale = "Autoscaled"
                
            display_env = env_id if len(env_id) <= 25 else env_id[:22] + "..."
            display_scale = scale if len(scale) <= 10 else scale[:7] + "..."
            display_image = image_version if len(image_version) <= 30 else image_version[:27] + "..."
            
            print(f"{display_env:<25} | {loc:<12} | {state:<8} | {display_scale:<10} | {display_image}")
            writer.writerow([env_id, loc, state, scale, image_version, gke_cluster, dag_bucket])

    print(f"      Found {len(env_list)} Composer Environments. Report saved to: {composer_csv}")
    print(f"\n✅ Cloud Composer Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_composer(project_input)
