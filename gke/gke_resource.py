import sys
import os
import csv
import warnings

try:
    from google.cloud import container_v1
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-container')
    from google.cloud import container_v1

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def audit_gke(project_id):
    print(f"\n🚀 Fetching GKE (Google Kubernetes Engine) Resources for project: {project_id}...")
    
    # Initialize GKE Client
    try:
        client = container_v1.ClusterManagerClient()
        parent = f"projects/{project_id}/locations/-"
        response = client.list_clusters(parent=parent)
        clusters = response.clusters
    except Exception as e:
        print(f"❌ Error fetching GKE clusters (API may be disabled): {e}")
        clusters = []

    # 1. CLUSTERS AUDIT
    print(f"\n[1/2] Scanning GKE Clusters...")
    clusters_csv = f"{project_id}_gke_clusters_audit.csv"
    nodepools_csv = f"{project_id}_gke_nodepools_audit.csv"
    cluster_count = 0
    nodepool_count = 0
    
    print(f"\n{'Cluster Name':<25} | {'Location':<15} | {'Master Ver':<15} | {'Status':<10} | {'Endpoint':<15} | {'Network'}")
    print("-" * 105)

    with open(clusters_csv, mode="w", newline="") as c_file, open(nodepools_csv, mode="w", newline="") as n_file:
        c_writer = csv.writer(c_file)
        n_writer = csv.writer(n_file)
        
        c_writer.writerow(["Cluster Name", "Location", "Master Version", "Status", "Endpoint", "Private Nodes", "Private Endpoint"])
        n_writer.writerow(["Cluster Name", "Node Pool Name", "Machine Type", "Disk Size (GB)", "Initial Node Count", "Autoscaling Enabled", "Min Nodes", "Max Nodes", "Auto Upgrade", "Auto Repair", "Status"])

        for cluster in clusters:
            cluster_count += 1
            name = cluster.name
            location = cluster.location
            version = cluster.current_master_version
            
            # Status check
            status = cluster.status.name if hasattr(cluster.status, 'name') else str(cluster.status)
            status = status.replace('STATUS_', '')
            
            endpoint = cluster.endpoint or "N/A"
            
            # Network visibility
            p_config = cluster.private_cluster_config
            private_nodes = "Yes" if p_config and p_config.enable_private_nodes else "No"
            private_endpoint = "Yes" if p_config and p_config.enable_private_endpoint else "No"
            network_type = "Private" if private_nodes == "Yes" else "Public"
            
            display_name = name if len(name) <= 25 else name[:22] + "..."
            display_endpoint = endpoint if len(endpoint) <= 15 else endpoint[:12] + "..."
            
            print(f"{display_name:<25} | {location:<15} | {version:<15} | {status:<10} | {display_endpoint:<15} | {network_type}")
            c_writer.writerow([name, location, version, status, endpoint, private_nodes, private_endpoint])
            
            # 2. NODE POOLS AUDIT
            for np in cluster.node_pools:
                nodepool_count += 1
                np_name = np.name
                machine_type = np.config.machine_type if np.config else "Unknown"
                disk_size = np.config.disk_size_gb if np.config else 0
                node_count = np.initial_node_count
                
                # Autoscaling
                auto_scale = "No"
                min_nodes, max_nodes = 0, 0
                if np.autoscaling and np.autoscaling.enabled:
                    auto_scale = "Yes"
                    min_nodes = np.autoscaling.min_node_count
                    max_nodes = np.autoscaling.max_node_count
                
                # Management settings
                auto_upgrade = "No"
                auto_repair = "No"
                if np.management:
                    auto_upgrade = "Yes" if np.management.auto_upgrade else "No"
                    auto_repair = "Yes" if np.management.auto_repair else "No"
                    
                np_status = np.status.name if hasattr(np.status, 'name') else str(np.status)
                np_status = np_status.replace('STATUS_', '')
                
                n_writer.writerow([name, np_name, machine_type, disk_size, node_count, auto_scale, min_nodes, max_nodes, auto_upgrade, auto_repair, np_status])

    if cluster_count == 0 and clusters:
        print("No GKE clusters found in this project.")
    print(f"      Found {cluster_count} GKE Clusters and {nodepool_count} Node Pools.")
    print(f"      Reports saved to: {clusters_csv} & {nodepools_csv}")

    print(f"\n✅ GKE Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_gke(project_input)
