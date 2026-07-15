import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import compute_v1
except ImportError:
    print("Missing required library. Run: pip install google-cloud-compute")
    sys.exit(1)

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_nat(project_id):
    print(f"\nFetching Cloud NAT Resources for project: {project_id}...")
    client = compute_v1.RoutersClient()

    # NAT gateways (embedded in Cloud Routers)
    nat_csv = f"{project_id}_cloud_nat_audit.csv"
    nat_count = 0
    router_count = 0
    with open(nat_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["NAT Name", "Router Name", "Region", "Network", "NAT IP Count", "NAT IPs", "Min Ports/VM", "Max Ports/VM", "Enable Dynamic Port Allocation", "Enable Endpoint Independent Mapping", "Enable Logging", "Log Filter", "ICMP Idle Timeout (s)", "TCP Established Idle Timeout (s)", "TCP Transitory Idle Timeout (s)", "UDP Idle Timeout (s)", "Source Subnet IP Ranges", "Drain NAT IPs"])
        try:
            for group in client.aggregated_list(project=project_id):
                region = group[0].replace("zones/", "").replace("regions/", "")
                for router in group[1].routers:
                    router_count += 1
                    network = router.network.split("/")[-1] if router.network else ""
                    if router.nats:
                        for nat in router.nats:
                            nat_count += 1
                            nat_ips = []
                            for ip in nat.nat_ips:
                                nat_ips.append(ip.split("/")[-1] if ip else "")
                            drain_ips = [ip.split("/")[-1] if ip else "" for ip in nat.drain_nat_ips] if nat.drain_nat_ips else []
                            source_ranges = []
                            if nat.source_subnetwork_ip_ranges_to_nat:
                                source_ranges = [r.name if hasattr(r, "name") else str(r) for r in nat.source_subnetwork_ip_ranges_to_nat]
                            writer.writerow([
                                nat.name,
                                router.name,
                                region,
                                network,
                                len(nat.nat_ips) if nat.nat_ips else 0,
                                ", ".join(nat_ips),
                                nat.min_ports_per_v_m,
                                nat.max_ports_per_v_m if hasattr(nat, "max_ports_per_v_m") else "",
                                nat.enable_dynamic_port_allocation if hasattr(nat, "enable_dynamic_port_allocation") else "",
                                nat.enable_endpoint_independent_mapping if hasattr(nat, "enable_endpoint_independent_mapping") else "",
                                nat.enable_logging if hasattr(nat, "enable_logging") else "",
                                nat.log_config.filter.name if hasattr(nat, "log_config") and nat.log_config else "",
                                nat.icmp_idle_timeout_sec,
                                nat.tcp_established_idle_timeout_sec,
                                nat.tcp_transitory_idle_timeout_sec,
                                nat.udp_idle_timeout_sec,
                                ", ".join(source_ranges),
                                ", ".join(drain_ips),
                            ])
                            print(f"  NAT: {nat.name}, Router: {router.name}, Region: {region}")
                    else:
                        print(f"  Router (no NAT): {router.name}, Region: {region}")
        except Exception as e:
            print(f"  Error listing routers/NAT: {e}")
    print(f"  Found {router_count} routers with {nat_count} NAT gateways. Report saved to: {nat_csv}")
    print("Cloud NAT Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_nat(project_input)
