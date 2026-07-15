import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import dataproc_v1
    from google.api_core import exceptions
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-dataproc')
    from google.cloud import dataproc_v1
    from google.api_core import exceptions

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_dataproc(project_id):
    print(f"\nFetching Dataproc Resources for project: {project_id}...")
    cluster_client = dataproc_v1.ClusterControllerClient()
    job_client = dataproc_v1.JobControllerClient()

    # Clusters
    cl_csv = f"{project_id}_dataproc_clusters_audit.csv"
    cl_count = 0
    with open(cl_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Cluster Name", "Region", "Status", "Image Version", "Component Gateway", "Master Machine", "Master Disk (GB)", "Worker Machine", "Worker Disk (GB)", "Min Workers", "Max Workers", "Initialization Actions", "Labels"])
        for region in ["us-central1", "us-east1", "us-west1", "europe-west1", "europe-west4", "asia-east1", "asia-southeast1"]:
            try:
                clusters = list(cluster_client.list_clusters(project_id=project_id, region=region))
                for c in clusters:
                    cl_count += 1
                    config = c.config if hasattr(c, "config") else None
                    mc = config.master_config if config else None
                    wc = config.worker_config if config else None
                    as_policy = ""
                    if config and config.autoscaling_config:
                        as_policy = config.autoscaling_config.policy_uri
                    init_actions = "; ".join([ia.executable_file for ia in config.initialization_actions]) if config and config.initialization_actions else ""
                    writer.writerow([
                        c.cluster_name,
                        region,
                        c.status.state.name if c.status and hasattr(c.status.state, "name") else str(c.status.state) if c.status else "",
                        config.software_config.image_version if config and config.software_config else "",
                        config.endpoint_config.enable_http_port_access if config and config.endpoint_config else "",
                        mc.machine_type_uri if mc else "",
                        mc.disk_config.boot_disk_size_gb if mc and mc.disk_config else "",
                        wc.machine_type_uri if wc else "",
                        wc.disk_config.boot_disk_size_gb if wc and wc.disk_config else "",
                        wc.min_num_instances if wc and hasattr(wc, "min_num_instances") else "",
                        wc.num_instances if wc else "",
                        init_actions,
                        str(dict(c.labels)) if c.labels else "",
                    ])
                    print(f"  Cluster: {c.cluster_name}, Region: {region}, Status: {c.status.state.name if c.status and hasattr(c.status.state, 'name') else ''}")
            except Exception:
                pass
    print(f"  Found {cl_count} clusters. Report saved to: {cl_csv}")

    # Jobs
    j_csv = f"{project_id}_dataproc_jobs_audit.csv"
    j_count = 0
    with open(j_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Job ID", "Cluster", "Region", "Type", "Status", "Create Time", "Finish Time"])
        for region in ["us-central1", "us-east1", "us-west1", "europe-west1", "europe-west4", "asia-east1", "asia-southeast1"]:
            try:
                jobs = list(job_client.list_jobs(project_id=project_id, region=region))
                for j in jobs:
                    j_count += 1
                    job_type = ""
                    if j.spark_job:
                        job_type = "Spark"
                    elif j.pyspark_job:
                        job_type = "PySpark"
                    elif j.hive_job:
                        job_type = "Hive"
                    elif j.pig_job:
                        job_type = "Pig"
                    elif j.spark_sql_job:
                        job_type = "SparkSQL"
                    elif j.flink_job:
                        job_type = "Flink"
                    elif j.trino_job:
                        job_type = "Trino"
                    writer.writerow([
                        j.reference.job_id if j.reference else "",
                        "",
                        region,
                        job_type,
                        j.status.state.name if j.status and hasattr(j.status.state, "name") else "",
                        j.status.state_start_time.strftime("%Y-%m-%d %H:%M:%S") if j.status and j.status.state_start_time else "",
                        "",
                    ])
            except Exception:
                pass
    print(f"  Found {j_count} jobs. Report saved to: {j_csv}")
    print("Dataproc Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_dataproc(project_input)
