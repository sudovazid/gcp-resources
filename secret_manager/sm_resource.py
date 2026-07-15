import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import secretmanager
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-secret-manager')
    from google.cloud import secretmanager

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def format_duration(duration_obj):
    if not duration_obj:
        return "N/A"
    seconds = getattr(duration_obj, "seconds", 0)
    if seconds == 0:
        return "0s"
    days = seconds // 86400
    if days > 0:
        return f"{days}d"
    hours = seconds // 3600
    return f"{hours}h"

def audit_secret_manager(project_id):
    print(f"\n🚀 Fetching Secret Manager Resources for project: {project_id}...")
    
    # Initialize Secret Manager Client
    try:
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project_id}"
        response = client.list_secrets(request={"parent": parent})
        secrets = list(response)
    except Exception as e:
        print(f"❌ Error fetching secrets (API may be disabled): {e}")
        secrets = []

    # 1. SECRETS AUDIT
    print(f"\n[1/1] Scanning Secrets & Version Lifecycles...")
    secrets_csv = f"{project_id}_secret_manager_audit.csv"
    secret_count = 0
    
    print(f"\n{'Secret Name':<35} | {'Replication':<12} | {'Rotation':<10} | {'Expiration':<10} | {'Active/Destroyed Versions'}")
    print("-" * 95)

    with open(secrets_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Secret Name", "Replication Type", "Rotation Period", "Expiration Time", "Enabled Versions", "Disabled Versions", "Destroyed Versions"])

        for secret in secrets:
            secret_count += 1
            name = extract_name(secret.name)
            
            # Replication
            rep_type = "Unknown"
            if secret.replication:
                if hasattr(secret.replication, 'automatic') and secret.replication.automatic:
                    rep_type = "Automatic"
                elif hasattr(secret.replication, 'user_managed') and secret.replication.user_managed:
                    rep_type = "User-Managed"
            
            # Rotation
            rotation = "None"
            if secret.rotation and secret.rotation.rotation_period:
                rotation = format_duration(secret.rotation.rotation_period)
            
            # Expiration
            expiration = "None"
            if secret.expire_time:
                try:
                    exp_dt = datetime.utcfromtimestamp(secret.expire_time.timestamp())
                    expiration = exp_dt.strftime("%Y-%m-%d")
                except Exception:
                    expiration = "Configured"
            
            # Audit versions
            enabled_count = 0
            disabled_count = 0
            destroyed_count = 0
            try:
                versions = client.list_secret_versions(request={"parent": secret.name})
                for version in versions:
                    state = version.state.name if hasattr(version.state, 'name') else str(version.state)
                    if "ENABLED" in state:
                        enabled_count += 1
                    elif "DISABLED" in state:
                        disabled_count += 1
                    elif "DESTROYED" in state:
                        destroyed_count += 1
            except Exception:
                pass

            display_name = name if len(name) <= 35 else name[:32] + "..."
            
            version_summary = f"{enabled_count} Active / {disabled_count} Disabled / {destroyed_count} Destroyed"
            print(f"{display_name:<35} | {rep_type:<12} | {rotation:<10} | {expiration:<10} | {version_summary}")
            writer.writerow([name, rep_type, rotation, expiration, enabled_count, disabled_count, destroyed_count])

    if secret_count == 0 and secrets:
        print("No Secrets found in this project.")
    print(f"      Found {secret_count} Secrets. Report saved to: {secrets_csv}")

    print(f"\n✅ Secret Manager Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_secret_manager(project_input)
