import csv
import os
import sys
import warnings

try:
    from google.cloud import artifactregistry_v1
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-artifact-registry')
    from google.cloud import artifactregistry_v1

# Silence the low-level gRPC C++ logs
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "3"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_artifact_registry(project_id):
    print(f"Fetching Artifact Registry Repositories and Storage Sizes for project: {project_id}...")

    client = artifactregistry_v1.ArtifactRegistryClient()
    
    # ADDED: "us", "eu", "asia" multi-regions to catch gcr.io mapped repositories!
    regions = [
        "global", "us", "eu", "asia", 
        "us-central1", "us-east1", "us-east4", "us-west1", "us-west2", 
        "europe-west1", "europe-west2", "europe-west4", 
        "asia-east1", "asia-southeast1", "asia-northeast1"
    ]

    print(f"\n{'Repository Name':<30} | {'Location':<13} | {'Format':<8} | {'Size (GB)':<9} | {'Cleanup'}")
    print("-" * 80)

    csv_file = f"{project_id}_artifact_registry_audit.csv"
    count = 0

    with open(csv_file, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Repository Name", "Location", "Format", "Size (GB)", "Description", "Cleanup Policies Enabled"])

        api_disabled_warned = False
        permission_denied_warned = False
        for region in regions:
            parent = f"projects/{project_id}/locations/{region}"
            try:
                request = artifactregistry_v1.ListRepositoriesRequest(parent=parent)
                
                for repo in client.list_repositories(request=request):
                    count += 1
                    
                    # Extract name and location
                    parts = repo.name.split('/')
                    location = parts[3]
                    name = parts[5]
                    display_name = name if len(name) <= 30 else name[:27] + "..."
                    
                    # Extract Format (e.g., DOCKER, PYTHON)
                    repo_format = repo.format_.name if hasattr(repo.format_, 'name') else str(repo.format_)
                    repo_format = repo_format.replace('Format.', '')

                    # Sum the sizes of all files in the repository
                    size_bytes = 0
                    try:
                        for file in client.list_files(parent=repo.name):
                            size_bytes += getattr(file, 'size_bytes', 0)
                    except Exception:
                        pass
                    size_gb = size_bytes / (1024**3)

                    # Check if Cleanup Policies exist
                    cleanup_enabled = "Yes" if repo.cleanup_policies else "No (Risk)"

                    print(f"{display_name:<30} | {location:<13} | {repo_format:<8} | {size_gb:>6.2f} GB | {cleanup_enabled}")
                    writer.writerow([name, location, repo_format, f"{size_gb:.2f}", repo.description, cleanup_enabled])
            except Exception as e:
                err_str = str(e)
                if ("api has not been used" in err_str.lower() or "disabled" in err_str.lower() or "service_disabled" in err_str.lower()) and not api_disabled_warned:
                    print(f"⚠️  Error listing repositories: Artifact Registry API is disabled in project '{project_id}'.")
                    print(f"   💡 Recommendation: Enable the API by running: gcloud services enable artifactregistry.googleapis.com --project {project_id}")
                    print(f"      Or visit: https://console.developers.google.com/apis/api/artifactregistry.googleapis.com/overview?project={project_id}")
                    api_disabled_warned = True
                elif ("permission" in err_str.lower() or "403" in err_str or "unauthorized" in err_str.lower()) and not permission_denied_warned:
                    print(f"⚠️  Error listing repositories: Access denied for project '{project_id}'.")
                    print(f"   💡 Recommendation: Ensure you have the 'Artifact Registry Reader' (roles/artifactregistry.reader) or 'Viewer' (roles/viewer) IAM role.")
                    permission_denied_warned = True

    if count == 0:
        print("No Artifact Registry repositories found in these regions.")
        
    print(f"\n✅ Artifact Registry Audit complete. {count} repositories saved to {csv_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Project ID argument missing.")
        sys.exit(1)

    project_id_arg = sys.argv[1]
    audit_artifact_registry(project_id_arg)
