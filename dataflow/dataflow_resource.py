import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import dataflow_v1beta3
except ImportError:
    print("Missing required library. Run: pip install google-cloud-dataflow-client")
    sys.exit(1)

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_dataflow(project_id):
    print(f"\nFetching Dataflow Resources for project: {project_id}...")
    client = dataflow_v1beta3.JobsV1Beta3Client()

    # Jobs
    j_csv = f"{project_id}_dataflow_jobs_audit.csv"
    j_count = 0
    with open(j_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job ID", "Name", "Type", "Current State", "Region", "Create Time", "Current State Time", "SDK", "Template File", "Template Type", "Autoscaling Algorithm", "Max Workers", "Num Workers", "Flex Resource Scheduling"])
        for location in ["us-central1", "us-east1", "us-west1", "europe-west1", "europe-west4", "asia-east1", "asia-southeast1"]:
            try:
                parent = f"projects/{project_id}/locations/{location}"
                jobs = list(client.list_jobs(project_id=project_id, location=location, filter_=dataflow_v1beta3.ListJobsRequest.Filter.ALL))
                for j in jobs:
                    j_count += 1
                    env = j.environment if hasattr(j, "environment") else None
                    sdk = env.user_agent.get("sdk_name", "") if env and env.user_agent else ""
                    template_type = env.user_agent.get("dataset_migration_type", "") if env and env.user_agent else ""
                    asp = j.environment.autoscaling_settings if hasattr(j, "environment") and j.environment and hasattr(j.environment, "autoscaling_settings") and j.environment.autoscaling_settings else None
                    flex_rs = ""
                    if hasattr(j, "flex_resource_scheduling_goal") and j.flex_resource_scheduling_goal:
                        flex_rs = j.flex_resource_scheduling_goal.name if hasattr(j.flex_resource_scheduling_goal, "name") else str(j.flex_resource_scheduling_goal)
                    writer.writerow([
                        j.id,
                        j.name,
                        j.type_.name if hasattr(j.type_, "name") else str(j.type_),
                        j.current_state.name if hasattr(j.current_state, "name") else str(j.current_state),
                        location,
                        j.create_time.strftime("%Y-%m-%d %H:%M:%S") if j.create_time else "",
                        j.current_state_time.strftime("%Y-%m-%d %H:%M:%S") if j.current_state_time else "",
                        sdk,
                        env.temp_storage_prefix if env else "",
                        template_type,
                        asp.algorithm.name if asp and hasattr(asp.algorithm, "name") else "",
                        asp.max_num_workers if asp else "",
                        env.num_workers if env else "",
                        flex_rs,
                    ])
                    print(f"  Job: {j.name}, State: {j.current_state.name if hasattr(j.current_state, 'name') else ''}, Location: {location}")
            except Exception:
                pass
    print(f"  Found {j_count} jobs. Report saved to: {j_csv}")
    print("Dataflow Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_dataflow(project_input)
