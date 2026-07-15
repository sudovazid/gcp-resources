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

def extract_location_and_id(resource_path):
    # Format: projects/{project_id}/locations/{location}/endpoints/{endpoint_id}
    parts = resource_path.split('/')
    if len(parts) >= 6:
        return parts[3], parts[5]
    return "Unknown", resource_path.split('/')[-1] if resource_path else "Unknown"

def audit_vertex(project_id):
    print(f"\n🚀 Fetching Vertex AI Resources for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('aiplatform', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Vertex AI client: {e}")
        return

    parent = f"projects/{project_id}/locations/-"
    endpoints_csv = f"{project_id}_vertex_endpoints_audit.csv"
    custom_jobs_csv = f"{project_id}_vertex_custom_jobs_audit.csv"
    datasets_csv = f"{project_id}_vertex_datasets_audit.csv"

    # 1. SCAN ENDPOINTS
    print(f"\n[1/3] Scanning Vertex AI Endpoints...")
    endpoints_list = []
    try:
        request = client.projects().locations().endpoints().list(parent=parent)
        while request is not None:
            response = request.execute()
            endpoints_list.extend(response.get('endpoints', []))
            request = client.projects().locations().endpoints().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Endpoints: {e}")

    print(f"\n{'Endpoint ID':<25} | {'Display Name':<25} | {'Location':<12} | {'Deployed Models Count'}")
    print("-" * 80)

    with open(endpoints_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Endpoint ID", "Display Name", "Location", "Create Time", "Deployed Model ID", "Model Display Name", "Machine Type", "Min Replicas", "Max Replicas"])

        for ep in endpoints_list:
            name_path = ep.get('name', '')
            loc, ep_id = extract_location_and_id(name_path)
            disp_name = ep.get('displayName', 'Unnamed')
            create_time = ep.get('createTime', 'Unknown')
            
            deployed_models = ep.get('deployedModels', [])
            disp_ep = ep_id if len(ep_id) <= 25 else ep_id[:22] + "..."
            disp_title = disp_name if len(disp_name) <= 25 else disp_name[:22] + "..."
            
            print(f"{disp_ep:<25} | {disp_title:<25} | {loc:<12} | {len(deployed_models)}")
            
            if not deployed_models:
                writer.writerow([ep_id, disp_name, loc, create_time, "N/A", "N/A", "N/A", 0, 0])
            else:
                for dm in deployed_models:
                    dm_id = dm.get('id', 'Unknown')
                    dm_disp = dm.get('displayName', 'Unnamed')
                    
                    # Scaling & machine details
                    dedicated = dm.get('dedicatedResources', {})
                    automatic = dm.get('automaticResources', {})
                    machine_type = dedicated.get('machineSpec', {}).get('machineType', 'N/A')
                    min_rep = dedicated.get('minReplicaCount') or automatic.get('minReplicaCount') or 0
                    max_rep = dedicated.get('maxReplicaCount') or automatic.get('maxReplicaCount') or 0
                    
                    writer.writerow([ep_id, disp_name, loc, create_time, dm_id, dm_disp, machine_type, min_rep, max_rep])

    print(f"      Found {len(endpoints_list)} Endpoints. Report saved to: {endpoints_csv}")

    # 2. SCAN CUSTOM JOBS
    print(f"\n[2/3] Scanning Vertex AI Custom Training Jobs...")
    custom_jobs_list = []
    try:
        request = client.projects().locations().customJobs().list(parent=parent)
        while request is not None:
            response = request.execute()
            custom_jobs_list.extend(response.get('customJobs', []))
            request = client.projects().locations().customJobs().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Custom Jobs: {e}")

    print(f"\n{'Job ID':<25} | {'Display Name':<25} | {'Location':<12} | {'State'}")
    print("-" * 80)

    with open(custom_jobs_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job ID", "Display Name", "Location", "State", "Create Time"])

        for job in custom_jobs_list:
            name_path = job.get('name', '')
            loc, job_id = extract_location_and_id(name_path)
            disp_name = job.get('displayName', 'Unnamed')
            state = job.get('state', 'Unknown')
            create_time = job.get('createTime', 'Unknown')
            
            disp_job = job_id if len(job_id) <= 25 else job_id[:22] + "..."
            disp_title = disp_name if len(disp_name) <= 25 else disp_name[:22] + "..."
            disp_state = state.replace('JOB_STATE_', '')
            
            print(f"{disp_job:<25} | {disp_title:<25} | {loc:<12} | {disp_state}")
            writer.writerow([job_id, disp_name, loc, state, create_time])

    print(f"      Found {len(custom_jobs_list)} Custom Jobs. Report saved to: {custom_jobs_csv}")

    # 3. SCAN DATASETS
    print(f"\n[3/3] Scanning Vertex AI Datasets...")
    datasets_list = []
    try:
        request = client.projects().locations().datasets().list(parent=parent)
        while request is not None:
            response = request.execute()
            datasets_list.extend(response.get('datasets', []))
            request = client.projects().locations().datasets().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Datasets: {e}")

    print(f"\n{'Dataset ID':<25} | {'Display Name':<25} | {'Location':<12} | {'Metadata Type'}")
    print("-" * 85)

    with open(datasets_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Dataset ID", "Display Name", "Location", "Metadata Schema Uri", "Create Time"])

        for dataset in datasets_list:
            name_path = dataset.get('name', '')
            loc, ds_id = extract_location_and_id(name_path)
            disp_name = dataset.get('displayName', 'Unnamed')
            schema_uri = dataset.get('metadataSchemaUri', 'N/A')
            create_time = dataset.get('createTime', 'Unknown')
            
            disp_ds = ds_id if len(ds_id) <= 25 else ds_id[:22] + "..."
            disp_title = disp_name if len(disp_name) <= 25 else disp_name[:22] + "..."
            
            # extract schema type name from URI
            schema_type = schema_uri.split('/')[-1] if '/' in schema_uri else schema_uri
            disp_schema = schema_type if len(schema_type) <= 20 else schema_type[:17] + "..."
            
            print(f"{disp_ds:<25} | {disp_title:<25} | {loc:<12} | {disp_schema}")
            writer.writerow([ds_id, disp_name, loc, schema_uri, create_time])

    print(f"      Found {len(datasets_list)} Datasets. Report saved to: {datasets_csv}")
    print(f"\n✅ Vertex AI Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_vertex(project_input)
