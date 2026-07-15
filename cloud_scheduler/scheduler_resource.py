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

def extract_location_and_job(resource_path):
    # Format: projects/{project_id}/locations/{location}/jobs/{job_id}
    parts = resource_path.split('/')
    if len(parts) >= 6:
        return parts[3], parts[5]
    return "Unknown", resource_path.split('/')[-1] if resource_path else "Unknown"

def audit_scheduler(project_id):
    print(f"\n🚀 Fetching Cloud Scheduler Resources for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('cloudscheduler', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Cloud Scheduler client: {e}")
        return

    jobs_csv = f"{project_id}_cloud_scheduler_jobs_audit.csv"
    jobs_list = []

    print(f"\n[1/1] Scanning Cloud Scheduler Jobs...")

    try:
        locations_list = client.projects().locations().list(parent=f"projects/{project_id}").execute()
        valid_locations = [loc['locationId'] for loc in locations_list.get('locations', [])]
    except Exception:
        valid_locations = ['us-central1', 'us-east1', 'us-west1', 'europe-west1', 'europe-west2', 'asia-east1', 'asia-northeast1']

    for loc in valid_locations:
        try:
            parent = f"projects/{project_id}/locations/{loc}"
            request = client.projects().locations().jobs().list(parent=parent)
            while request is not None:
                response = request.execute()
                jobs_list.extend(response.get('jobs', []))
                request = client.projects().locations().jobs().list_next(request, response)
        except Exception:
            pass

    print(f"\n{'Job ID':<25} | {'Location':<12} | {'State':<8} | {'Schedule':<12} | {'Target Type':<12} | {'Last Attempt status'}")
    print("-" * 105)

    with open(jobs_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job ID", "Location", "State", "Schedule", "TimeZone", "Target Type", "Target Destination", "Last Attempt Time", "Last Attempt Status"])

        for job in jobs_list:
            name_path = job.get('name', '')
            loc, job_id = extract_location_and_job(name_path)
            state = job.get('state', 'Unknown')
            schedule = job.get('schedule', 'N/A')
            timezone = job.get('timeZone', 'UTC')
            
            # Determine target
            target_type = "Unknown"
            target_dest = "N/A"
            if 'pubsubTarget' in job:
                target_type = "Pub/Sub"
                target_dest = job['pubsubTarget'].get('topicName', 'Unknown')
            elif 'httpTarget' in job:
                target_type = "HTTP"
                target_dest = job['httpTarget'].get('uri', 'Unknown')
            elif 'appEngineHttpTarget' in job:
                target_type = "App Engine"
                target_dest = job['appEngineHttpTarget'].get('relativeUri', 'Unknown')
            
            last_attempt = job.get('lastAttemptTime', 'Never')
            
            # Extract last attempt status
            status_obj = job.get('status', {})
            status_code = status_obj.get('code', 0)
            if status_code == 0:
                last_status = "Success"
            else:
                last_status = status_obj.get('message', f"Failed (Code: {status_code})")
                
            display_job = job_id if len(job_id) <= 25 else job_id[:22] + "..."
            display_schedule = schedule if len(schedule) <= 12 else schedule[:9] + "..."
            display_status = last_status if len(last_status) <= 25 else last_status[:22] + "..."
            
            print(f"{display_job:<25} | {loc:<12} | {state:<8} | {display_schedule:<12} | {target_type:<12} | {display_status}")
            
            writer.writerow([job_id, loc, state, schedule, timezone, target_type, target_dest, last_attempt, last_status])

    print(f"      Found {len(jobs_list)} Cloud Scheduler Jobs. Report saved to: {jobs_csv}")
    print(f"\n✅ Cloud Scheduler Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_scheduler(project_input)
