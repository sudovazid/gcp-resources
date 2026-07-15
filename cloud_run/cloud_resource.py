import csv
import os
import sys
import warnings
import subprocess

from google.cloud import run_v2

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")


def audit_cloud_run(project_id):
    active_regions = set()

    # ==========================================
    # 1. CLOUD RUN SERVICES
    # ==========================================
    print(f"Fetching Cloud Run Services for project: {project_id}...")

    parent = f"projects/{project_id}/locations/-"
    services_client = run_v2.ServicesClient()

    try:
        request = run_v2.ListServicesRequest(parent=parent)
        services = services_client.list_services(request=request)
    except Exception as e:
        err_str = str(e)
        print(f"❌ Error fetching Cloud Run services: {err_str}")
        if "api has not been used" in err_str.lower() or "disabled" in err_str.lower() or "service_disabled" in err_str.lower():
            print(f"   💡 Recommendation: The 'Cloud Run Admin API' is currently disabled in project '{project_id}'.")
            print(f"      Please enable it by running: gcloud services enable run.googleapis.com --project {project_id}")
            print(f"      Or visit: https://console.developers.google.com/apis/api/run.googleapis.com/overview?project={project_id}")
        elif "permission" in err_str.lower() or "403" in err_str:
            print(f"   💡 Recommendation: The authenticated identity lacks permission to list Cloud Run services.")
            print(f"      Please ensure you have the 'Cloud Run Viewer' (roles/run.viewer) or 'Viewer' (roles/viewer) role.")
        services = []

    print(
        f"\n{'Service Name':<35} | {'Region':<13} | {'CPU/Mem':<10} | {'Min/Max':<7} | {'Concur':<6}"
    )
    print("-" * 83)

    services_csv = f"{project_id}_cloudrun_services_audit.csv"
    count = 0
    with open(services_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Service Name",
                "Region",
                "CPU",
                "Memory",
                "Min Instances",
                "Max Instances",
            ]
        )

        for service in services:
            count += 1
            parts = service.name.split("/")
            region = parts[3]
            active_regions.add(region)

            svc_name = parts[5]
            display_name = svc_name if len(svc_name) <= 35 else svc_name[:32] + "..."

            cpu, memory = "N/A", "N/A"
            if service.template.containers:
                res = service.template.containers[0].resources
                cpu = res.limits.get("cpu", "N/A")
                memory = res.limits.get("memory", "N/A")

            min_inst = service.template.scaling.min_instance_count
            max_inst = service.template.scaling.max_instance_count
            concur = service.template.max_instance_request_concurrency

            print(
                f"{display_name:<35} | {region:<13} | {f'{cpu}/{memory}':<10} | {f'{min_inst}/{max_inst}':<7} | {concur:<6}"
            )
            writer.writerow([svc_name, region, cpu, memory, min_inst, max_inst])

    print(f"\n✅ Cloud Run Services complete. {count} services saved to {services_csv}")

    # Fallback if no services were found to establish active regions
    if not active_regions:
        active_regions = {
            "us-central1",
            "us-east1",
            "us-west1",
            "europe-west1",
            "asia-northeast1",
        }

    # ==========================================
    # 2. CLOUD RUN JOBS
    # ==========================================
    print(f"\nFetching Cloud Run Jobs for project: {project_id}...")
    jobs_client = run_v2.JobsClient()

    print(
        f"\n{'Job Name':<35} | {'Region':<13} | {'CPU/Mem':<10} | {'Tasks':<5} | {'Retries':<7}"
    )
    print("-" * 83)

    jobs_csv = f"{project_id}_cloudrun_jobs_audit.csv"
    job_count = 0
    with open(jobs_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Job Name", "Region", "CPU", "Memory", "Task Count", "Max Retries"]
        )

        # Iterate over active regions (Jobs API doesn't support the global '-' wildcard)
        for region in active_regions:
            regional_parent = f"projects/{project_id}/locations/{region}"
            try:
                request = run_v2.ListJobsRequest(parent=regional_parent)
                for job in jobs_client.list_jobs(request=request):
                    job_count += 1
                    parts = job.name.split("/")
                    job_name = parts[5]
                    display_name = (
                        job_name if len(job_name) <= 35 else job_name[:32] + "..."
                    )

                    cpu, memory = "N/A", "N/A"
                    if job.template.template.containers:
                        res = job.template.template.containers[0].resources
                        cpu = res.limits.get("cpu", "N/A")
                        memory = res.limits.get("memory", "N/A")

                    task_count = job.template.task_count
                    max_retries = job.template.template.max_retries

                    print(
                        f"{display_name:<35} | {region:<13} | {f'{cpu}/{memory}':<10} | {task_count:<5} | {max_retries:<7}"
                    )
                    writer.writerow(
                        [job_name, region, cpu, memory, task_count, max_retries]
                    )
            except Exception:
                pass  # Skip regions that fail or don't exist

    print(f"\n✅ Cloud Run Jobs complete. {job_count} jobs saved to {jobs_csv}")

    # ==========================================
    # 3. DOMAIN MAPPINGS
    # ==========================================
    print(f"\nFetching Cloud Run Domain Mappings for project: {project_id}...")

    dm_csv_file = f"{project_id}_cloudrun_domain_mappings_audit.csv"
    command = [
        "gcloud", "run", "domain-mappings", "list",
        f"--project={project_id}",
        "--format=csv(DOMAIN,SERVICE,REGION)"
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        reader = csv.reader(result.stdout.strip().splitlines())
        header = next(reader)
        domain_mappings = list(reader)

        print(f"\n{'Domain':<40} | {'Service':<25} | {'Region':<15}")
        print("-" * 83)

        with open(dm_csv_file, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(domain_mappings)

        for row in domain_mappings:
            domain, service, region = row
            display_domain = domain if len(domain) <= 38 else domain[:35] + "..."
            display_service = service if len(service) <= 23 else service[:20] + "..."
            print(f"{display_domain:<40} | {display_service:<25} | {region:<15}")

        print(f"\n✅ Cloud Run Domain Mappings complete. {len(domain_mappings)} mappings saved to {dm_csv_file}")

    except FileNotFoundError:
        print("   ⚠️ gcloud command not found. Skipping domain mappings.")
    except subprocess.CalledProcessError as e:
        if "API is not enabled" in e.stderr:
            print("   💡 Recommendation: The 'Cloud Run Admin API' is not enabled.")
        else:
            print(f"   ❌ Error fetching domain mappings: {e.stderr}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Project ID argument missing.")
        sys.exit(1)

    project_id_arg = sys.argv[1]
    audit_cloud_run(project_id_arg)
