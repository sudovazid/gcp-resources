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

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def audit_app_engine(project_id):
    print(f"\n🚀 Fetching App Engine Resources for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('appengine', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing App Engine client: {e}")
        return

    # 1. APPLICATION AUDIT
    print(f"\n[1/2] Scanning App Engine Application...")
    app_csv = f"{project_id}_app_engine_app_audit.csv"
    versions_csv = f"{project_id}_app_engine_versions_audit.csv"
    
    try:
        app = client.apps().get(appsId=project_id).execute()
        location = app.get('locationId', 'Unknown')
        status = app.get('servingStatus', 'Unknown')
        hostname = app.get('defaultHostname', 'N/A')
        print(f"\n{'App Engine ID':<25} | {'Location':<15} | {'Status':<15} | {'Hostname'}")
        print("-" * 80)
        print(f"{project_id:<25} | {location:<15} | {status:<15} | {hostname}")
        
        with open(app_csv, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["App Engine ID", "Location", "Serving Status", "Default Hostname"])
            writer.writerow([project_id, location, status, hostname])
    except Exception:
        print("⚠️ No App Engine application found or access denied.")
        return

    # 2. SERVICES & VERSIONS AUDIT
    print(f"\n[2/2] Scanning App Engine Services & Versions...")
    service_count = 0
    version_count = 0
    
    try:
        services_response = client.apps().services().list(appsId=project_id).execute()
        services = services_response.get('services', [])
    except Exception as e:
        print(f"❌ Error listing App Engine services: {e}")
        services = []

    print(f"\n{'Service Name':<15} | {'Version ID':<20} | {'Runtime':<12} | {'Status':<10} | {'Class':<6} | {'Scaling'}")
    print("-" * 75)

    with open(versions_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Service Name", "Version ID", "Runtime", "Serving Status", "Instance Class", "Scaling Type", "Created By", "Create Time"])

        for svc in services:
            service_count += 1
            svc_id = svc.get('id')
            
            try:
                versions_response = client.apps().services().versions().list(appsId=project_id, servicesId=svc_id).execute()
                versions = versions_response.get('versions', [])
            except Exception:
                versions = []

            for ver in versions:
                version_count += 1
                ver_id = ver.get('id')
                runtime = ver.get('runtime', 'Unknown')
                ver_status = ver.get('servingStatus', 'Unknown')
                inst_class = ver.get('instanceClass', 'N/A')
                created_by = ver.get('createdBy', 'N/A')
                create_time = ver.get('createTime', 'N/A')
                
                # Determine scaling
                scaling = "Unknown"
                if 'automaticScaling' in ver:
                    scaling = "Automatic"
                elif 'manualScaling' in ver:
                    scaling = "Manual"
                elif 'basicScaling' in ver:
                    scaling = "Basic"
                
                display_svc = svc_id if len(svc_id) <= 15 else svc_id[:12] + "..."
                display_ver = ver_id if len(ver_id) <= 20 else ver_id[:17] + "..."
                
                print(f"{display_svc:<15} | {display_ver:<20} | {runtime:<12} | {ver_status:<10} | {inst_class:<6} | {scaling}")
                writer.writerow([svc_id, ver_id, runtime, ver_status, inst_class, scaling, created_by, create_time])

    print(f"      Found {service_count} Services and {version_count} Deployment Versions.")
    print(f"      Reports saved to: {app_csv} & {versions_csv}")

    print(f"\n✅ App Engine Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_app_engine(project_input)
