import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import tasks_v2
    from google.api_core import exceptions
except ImportError:
    print("Missing required library. Run: pip install google-cloud-tasks")
    sys.exit(1)

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_tasks(project_id):
    print(f"\nFetching Cloud Tasks Resources for project: {project_id}...")
    client = tasks_v2.CloudTasksClient()

    # List regions that have queues
    q_csv = f"{project_id}_cloud_tasks_queues_audit.csv"
    q_count = 0
    with open(q_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Queue Name", "Location", "State", "Max Dispatches/s", "Max Concurrent", "Max Retry Attempts", "Max Retry Duration (s)", "Min Backoff (s)", "Max Backoff (s)", "Max Doublings", "Stackdriver Logging", "Target Type", "Target URI", "Pull Target", "Create Time"])
        try:
            parent = f"projects/{project_id}/locations/-"
            queues = list(client.list_queues(parent=parent))
            for q in queues:
                q_count += 1
                loc = q.name.split("/")[-3] if "/locations/" in q.name else ""
                rd = q.retry_config if hasattr(q, "retry_config") and q.retry_config else None
                target_type = ""
                target_uri = ""
                if q.app_engine_routing_override and q.app_engine_routing_override.service:
                    target_type = "App Engine"
                    target_uri = q.app_engine_routing_override.service
                elif q.http_target:
                    target_type = "HTTP"
                    target_uri = ""
                elif q.pull_target:
                    target_type = "Pull"
                writer.writerow([
                    q.name.split("/")[-1],
                    loc,
                    q.state.name if hasattr(q.state, "name") else str(q.state),
                    q.rate_limits.max_dispatches_per_second if q.rate_limits else "",
                    q.rate_limits.max_concurrent_dispatches if q.rate_limits else "",
                    rd.max_attempts if rd else "",
                    rd.max_retry_duration.total_seconds() if rd and rd.max_retry_duration else "",
                    rd.min_backoff.total_seconds() if rd and rd.min_backoff else "",
                    rd.max_backoff.total_seconds() if rd and rd.max_backoff else "",
                    rd.max_doublings if rd else "",
                    q.stackdriver_logging_config.sampling_ratio if hasattr(q, "stackdriver_logging_config") and q.stackdriver_logging_config else "",
                    target_type,
                    target_uri,
                    "Yes" if q.pull_target else "",
                    q.create_time.strftime("%Y-%m-%d %H:%M:%S") if q.create_time else "",
                ])
                print(f"  Queue: {q.name.split('/')[-1]}, Location: {loc}, State: {q.state.name if hasattr(q.state, 'name') else ''}")
        except Exception as e:
            print(f"  Error listing queues: {e}")
    print(f"  Found {q_count} queues. Report saved to: {q_csv}")

    # Tasks in each queue
    t_csv = f"{project_id}_cloud_tasks_tasks_audit.csv"
    t_count = 0
    with open(t_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Queue Name", "Task Name", "Schedule Time", "Create Time", "Dispatch Count", "Last Attempt Time", "Response Status"])
        try:
            parent = f"projects/{project_id}/locations/-"
            queues = list(client.list_queues(parent=parent))
            for q in queues:
                try:
                    tasks = list(client.list_tasks(parent=q.name))
                    for t in tasks:
                        t_count += 1
                        last_attempt = None
                        status = ""
                        if hasattr(t, "last_attempt") and t.last_attempt:
                            last_attempt = t.last_attempt.schedule_time.strftime("%Y-%m-%d %H:%M:%S") if t.last_attempt.schedule_time else ""
                            status = t.last_attempt.response_status.code if t.last_attempt.response_status else ""
                        writer.writerow([
                            q.name.split("/")[-1],
                            t.name.split("/")[-1],
                            t.schedule_time.strftime("%Y-%m-%d %H:%M:%S") if t.schedule_time else "",
                            t.create_time.strftime("%Y-%m-%d %H:%M:%S") if t.create_time else "",
                            t.dispatch_count,
                            last_attempt,
                            status,
                        ])
                except Exception:
                    pass
        except Exception:
            pass
    print(f"  Found {t_count} tasks. Report saved to: {t_csv}")
    print("Cloud Tasks Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_tasks(project_input)
