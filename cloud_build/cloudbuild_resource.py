import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud.devtools import cloudbuild_v1
    from google.api_core import exceptions
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-build')
    from google.cloud.devtools import cloudbuild_v1
    from google.api_core import exceptions

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_cloudbuild(project_id):
    print(f"\nFetching Cloud Build Resources for project: {project_id}...")

    # Triggers
    trig_csv = f"{project_id}_cloudbuild_triggers_audit.csv"
    try:
        client = cloudbuild_v1.CloudBuildClient()
        parent = f"projects/{project_id}/locations/global"
        triggers = list(client.list_build_triggers(parent=parent))
    except Exception:
        try:
            from google.cloud.devtools import cloudbuild_v2
            client = cloudbuild_v2.CloudBuildClient()
            try:
                parent = f"projects/{project_id}/locations/global"
                triggers = list(client.list_build_triggers(parent=parent))
            except Exception:
                parent = f"projects/{project_id}"
                triggers = list(client.list_build_triggers(parent=parent))
        except Exception:
            triggers = []

    trig_count = 0
    with open(trig_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Trigger Name", "Description", "Filename / Config", "Source Repo", "Source Branch", "Source Tag", "Source PR", "Substitutions", "Ignored Files", "Included Files", "Create Time", "Disabled"])
        for t in triggers:
            trig_count += 1
            source = ""
            branch = ""
            tag = ""
            pr = ""
            if t.github:
                source = "GitHub"
                if t.github.pull_request:
                    pr = t.github.pull_request.branch or ""
                elif t.github.push:
                    branch = t.github.push.branch or ""
                    tag = t.github.push.tag or ""
            elif t.pubsub_config:
                source = "Pub/Sub"
            elif t.webhook_config:
                source = "Webhook"
            elif t.source_to_build:
                source = t.source_to_build.repo_source or ""
                branch = t.source_to_build.repo_branch or ""
                tag = t.source_to_build.repo_tag or ""
            filename = ""
            if hasattr(t, "build") and t.build:
                filename = t.build.steps[0].name if t.build.steps else ""
            elif hasattr(t, "filename"):
                filename = t.filename
            writer.writerow([
                t.name.split("/")[-1] if "/" in (t.name or "") else t.name,
                t.description,
                filename,
                source,
                branch,
                tag,
                pr,
                str(t.substitutions) if t.substitutions else "",
                ", ".join(t.ignored_files) if t.ignored_files else "",
                ", ".join(t.included_files) if t.included_files else "",
                t.create_time.strftime("%Y-%m-%d %H:%M:%S") if t.create_time else "",
                t.disabled,
            ])
            print(f"  Trigger: {t.name.split('/')[-1] if '/' in (t.name or '') else t.name}, Source: {source}")
    print(f"  Found {trig_count} triggers. Report saved to: {trig_csv}")

    # Recent builds
    b_csv = f"{project_id}_cloudbuild_builds_audit.csv"
    b_count = 0
    with open(b_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Build ID", "Trigger ID", "Status", "Source", "Branch/Commit", "Images", "Create Time", "Finish Time", "Logs Bucket", "Timeout (s)", "Machine Type"])
        try:
            client = cloudbuild_v1.CloudBuildClient()
            builds = list(client.list_builds(project_id=project_id, page_size=50))
            for b in builds:
                b_count += 1
                source_str = ""
                branch = ""
                if b.source and b.source.repo_source:
                    source_str = b.source.repo_source.repo_name or ""
                    branch = b.source.repo_source.branch_name or ""
                elif b.source and b.source.storage_source:
                    source_str = b.source.storage_source.bucket or ""
                writer.writerow([
                    b.id,
                    b.build_trigger_id,
                    b.status.name if hasattr(b.status, "name") else str(b.status),
                    source_str,
                    branch,
                    ", ".join(b.images) if b.images else "",
                    b.create_time.strftime("%Y-%m-%d %H:%M:%S") if b.create_time else "",
                    b.finish_time.strftime("%Y-%m-%d %H:%M:%S") if b.finish_time else "",
                    b.logs_bucket,
                    b.timeout.total_seconds() if b.timeout else "",
                    b.options.machine_type.name if b.options and b.options.machine_type else "",
                ])
        except Exception:
            pass
    print(f"  Found {b_count} builds. Report saved to: {b_csv}")
    print("Cloud Build Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_cloudbuild(project_input)
