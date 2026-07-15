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

# Silence low-level warnings & gRPC C++ logs
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

# Set of APIs enabled by default on standard GCP projects
DEFAULT_ENABLED_APIS = {
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "cloudapis.googleapis.com",
    "cloudbilling.googleapis.com",
    "clouddebugger.googleapis.com",
    "clouderrorreporting.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "datastore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "oslogin.googleapis.com",
    "servicecontrol.googleapis.com",
    "servicemanagement.googleapis.com",
    "serviceusage.googleapis.com",
    "sql-component.googleapis.com",
    "storage-api.googleapis.com",
    "storage-component.googleapis.com",
    "storage.googleapis.com",
    "containerregistry.googleapis.com"
}

def audit_enabled_apis(project_id):
    print(f"\n🚀 Fetching Enabled APIs and Services for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('serviceusage', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Service Usage client: {e}")
        return

    services_csv = f"{project_id}_enabled_apis_audit.csv"
    services_list = []

    print(f"\n[1/1] Scanning Service Usage API...")

    try:
        parent = f"projects/{project_id}"
        request = client.services().list(parent=parent, filter="state:ENABLED")
        while request is not None:
            response = request.execute()
            services_list.extend(response.get('services', []))
            request = client.services().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Enabled APIs: {e}")
        return

    # Print table header
    print(f"\n{'Service Name':<45} | {'Service Title':<45} | {'Source'}")
    print("-" * 110)

    # Sort services so User Enabled ones come first, then GCP (Default)
    sorted_services = []
    for service in services_list:
        config = service.get('config', {})
        name = config.get('name', service.get('name', '').split('/')[-1])
        title = config.get('title', name)
        
        source = "GCP (Default)" if name in DEFAULT_ENABLED_APIS else "User Enabled"
        sorted_services.append((name, title, source))
    
    # Sort first by source (User Enabled first), then by name
    sorted_services.sort(key=lambda x: (0 if x[2] == "User Enabled" else 1, x[0]))

    user_count = 0
    gcp_count = 0

    with open(services_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Service Name", "Service Title", "State", "Enablement Source"])

        for name, title, source in sorted_services:
            display_name = name if len(name) <= 45 else name[:42] + "..."
            display_title = title if len(title) <= 45 else title[:42] + "..."
            
            if source == "User Enabled":
                user_count += 1
            else:
                gcp_count += 1

            print(f"{display_name:<45} | {display_title:<45} | {source}")
            writer.writerow([name, title, "ENABLED", source])

    print(f"\nAudit completed: Found {len(services_list)} enabled APIs:")
    print(f" - User Enabled: {user_count}")
    print(f" - GCP Default:  {gcp_count}")
    print(f"Report saved to: {services_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_enabled_apis(project_input)
