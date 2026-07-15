import csv
import os
import sys
import warnings

try:
    from google.cloud import compute_v1
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-compute')
    from google.cloud import compute_v1

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "3"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    """Helper to extract the last part of a GCP resource URL"""
    return url.split('/')[-1] if url else "Unknown"

def handle_compute_error(error, resource_area, project_id):
    err_str = str(error)
    print(f"❌ Error scanning {resource_area}: {err_str}")
    if "403" in err_str or "permission" in err_str.lower() or "denied" in err_str.lower():
        print(f"   💡 Recommendation: The authenticated identity lacks permission to list {resource_area.lower()}.")
        print(f"      Please grant the 'Compute Viewer' (roles/compute.viewer) or 'Viewer' (roles/viewer) IAM role")
        print(f"      to your active user/service account on project '{project_id}' and run the audit again.")

def audit_compute_engine(project_id):
    print(f"\n🚀 Fetching Compute Engine & Network Resources for: {project_id}...")
    
    # Initialize Clients
    try:
        instances_client = compute_v1.InstancesClient()
        disks_client = compute_v1.DisksClient()
        snapshots_client = compute_v1.SnapshotsClient()
        images_client = compute_v1.ImagesClient()
        machine_images_client = compute_v1.MachineImagesClient()
        templates_client = compute_v1.InstanceTemplatesClient()
        networks_client = compute_v1.NetworksClient()
        health_checks_client = compute_v1.HealthChecksClient()
    except Exception as e:
        print(f"❌ Error initializing Compute Engine clients: {e}")
        return

    # ==========================================
    # 1. COMPUTE RESOURCES (VMs & Templates)
    # ==========================================
    print(f"\n[1/3] Scanning Virtual Machines & Templates...")
    compute_csv = f"{project_id}_gce_compute_audit.csv"
    vm_count, template_count = 0, 0
    
    try:
        with open(compute_csv, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Resource Type", "Name", "Zone", "Machine Type / Info", "State"])

            # Fetch VMs using Aggregated List (Searches all zones instantly)
            request = compute_v1.AggregatedListInstancesRequest(project=project_id)
            for zone, response in instances_client.aggregated_list(request=request):
                if response.instances:
                    zone_name = extract_name(zone)
                    for vm in response.instances:
                        vm_count += 1
                        machine_type = extract_name(vm.machine_type)
                        writer.writerow(["VM Instance", vm.name, zone_name, machine_type, vm.status])

            # Fetch Instance Templates
            for template in templates_client.list(project=project_id):
                template_count += 1
                machine_type = extract_name(template.properties.machine_type)
                writer.writerow(["Instance Template", template.name, "Global", machine_type, "READY"])

        print(f"      Found {vm_count} VMs and {template_count} Instance Templates.")
    except Exception as e:
        handle_compute_error(e, "Compute resources (VMs/Templates)", project_id)

    # ==========================================
    # 2. STORAGE RESOURCES (Disks, Snapshots, Images)
    # ==========================================
    print(f"[2/3] Scanning Storage (Disks, Snapshots, Images)...")
    storage_csv = f"{project_id}_gce_storage_audit.csv"
    disk_count, snap_count, image_count, mi_count = 0, 0, 0, 0

    try:
        with open(storage_csv, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Resource Type", "Name", "Zone/Location", "Size (GB)", "State"])

            # Fetch Disks (Volumes)
            disk_req = compute_v1.AggregatedListDisksRequest(project=project_id)
            for zone, response in disks_client.aggregated_list(request=disk_req):
                if response.disks:
                    zone_name = extract_name(zone)
                    for disk in response.disks:
                        disk_count += 1
                        writer.writerow(["Disk", disk.name, zone_name, disk.size_gb, disk.status])

            # Fetch Snapshots
            for snap in snapshots_client.list(project=project_id):
                snap_count += 1
                writer.writerow(["Snapshot", snap.name, "Global", snap.disk_size_gb, snap.status])

            # Fetch Custom Images
            for image in images_client.list(project=project_id):
                image_count += 1
                writer.writerow(["Custom Image", image.name, "Global", image.disk_size_gb, image.status])
                
            # Fetch Machine Images
            for mi in machine_images_client.list(project=project_id):
                mi_count += 1
                writer.writerow(["Machine Image", mi.name, "Global", "N/A", mi.status])

        print(f"      Found {disk_count} Disks, {snap_count} Snapshots, {image_count} Images, {mi_count} Machine Images.")
    except Exception as e:
        handle_compute_error(e, "Storage resources (Disks/Snapshots/Images)", project_id)

    # ==========================================
    # 3. NETWORKING & HEALTH (VPCs, Health Checks)
    # ==========================================
    print(f"[3/3] Scanning Networking & Health Checks...")
    network_csv = f"{project_id}_gce_network_audit.csv"
    net_count, hc_count = 0, 0

    try:
        with open(network_csv, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Resource Type", "Name", "Routing Mode / Protocol", "Subnets Count"])

            # Fetch VPC Networks
            for net in networks_client.list(project=project_id):
                net_count += 1
                subnets = len(net.subnetworks) if net.subnetworks else 0
                writer.writerow(["VPC Network", net.name, net.routing_config.routing_mode, subnets])

            # Fetch Health Checks
            for hc in health_checks_client.list(project=project_id):
                hc_count += 1
                protocol = hc.type_
                writer.writerow(["Health Check", hc.name, protocol, "N/A"])

        print(f"      Found {net_count} VPC Networks and {hc_count} Health Checks.")
    except Exception as e:
        handle_compute_error(e, "Network resources", project_id)
    print(f"\n✅ Compute & Network Audit complete! Saved 3 CSV reports.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Project ID argument missing.")
        sys.exit(1)

    project_id_arg = sys.argv[1]
    audit_compute_engine(project_id_arg)
