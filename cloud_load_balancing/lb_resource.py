import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import compute_v1
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-compute')
    from google.cloud import compute_v1

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_load_balancing(project_id):
    print(f"\nFetching Cloud Load Balancing Resources for project: {project_id}...")

    # Forwarding rules
    fr_csv = f"{project_id}_lb_forwarding_rules_audit.csv"
    fr_count = 0
    with open(fr_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Region", "IP Address", "IP Protocol", "Port Range", "Target", "Load Balancing Scheme", "Network Tier", "Network", "Subnetwork", "Allow Global Access", "Description"])
        client = compute_v1.ForwardingRulesClient()
        try:
            for group in client.aggregated_list(project=project_id):
                region = group[0].replace("zones/", "").replace("regions/", "")
                for fr in group[1].forwarding_rules:
                    fr_count += 1
                    def get_fr_field(obj, *names):
                        for n in names:
                            try:
                                return getattr(obj, n)
                            except Exception:
                                continue
                        return ""
                    writer.writerow([
                        fr.name,
                        region,
                        get_fr_field(fr, 'ip_address', 'IPAddress'),
                        get_fr_field(fr, 'ip_protocol', 'IPProtocol'),
                        get_fr_field(fr, 'port_range', 'portRange'),
                        fr.target,
                        get_fr_field(fr, 'load_balancing_scheme', 'loadBalancingScheme'),
                        get_fr_field(fr, 'network_tier', 'networkTier'),
                        fr.network.split("/")[-1] if fr.network else "",
                        fr.subnetwork.split("/")[-1] if fr.subnetwork else "",
                        get_fr_field(fr, 'allow_global_access', 'allowGlobalAccess'),
                        fr.description,
                    ])
        except Exception as e:
            print(f"  Error listing forwarding rules: {e}")
    print(f"  Found {fr_count} forwarding rules. Report saved to: {fr_csv}")

    # Backend services
    bs_csv = f"{project_id}_lb_backend_services_audit.csv"
    bs_count = 0
    with open(bs_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Region", "Protocol", "Scheme", "Health Checks", "Session Affinity", "Timeout (s)", "Enable CDN", "Backend Groups"])
        bs_client = compute_v1.BackendServicesClient()
        try:
            for group in bs_client.aggregated_list(project=project_id):
                region = group[0].replace("zones/", "").replace("regions/", "")
                for bs in group[1].backend_services:
                    bs_count += 1
                    def get_bs_field(obj, *names):
                        for n in names:
                            try:
                                return getattr(obj, n)
                            except Exception:
                                continue
                        return []
                    hcs = ", ".join(bs.health_checks) if bs.health_checks else ""
                    backends_field = get_bs_field(bs, 'backend', 'backends')
                    backends = "; ".join([f"{b.group.split('/')[-1]}" for b in backends_field]) if backends_field else ""
                    writer.writerow([
                        bs.name,
                        region if region != "global" else "Global",
                        bs.protocol,
                        bs.load_balancing_scheme,
                        hcs,
                        bs.session_affinity,
                        bs.timeout_sec,
                        bs.enable_c_d_n,
                        backends,
                    ])
        except Exception as e:
            print(f"  Error listing backend services: {e}")
    print(f"  Found {bs_count} backend services. Report saved to: {bs_csv}")

    # Target proxies
    tp_csv = f"{project_id}_lb_target_proxies_audit.csv"
    tp_count = 0
    with open(tp_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Type", "Region", "URL Map", "SSL Certificate", "Quic Override"])
        for proxy_cls, ptype in [
            (compute_v1.TargetHttpProxiesClient(), "HTTP"),
            (compute_v1.TargetHttpsProxiesClient(), "HTTPS"),
            (compute_v1.TargetTcpProxiesClient(), "TCP"),
            (compute_v1.TargetSslProxiesClient(), "SSL"),
            (compute_v1.TargetGrpcProxiesClient(), "gRPC"),
        ]:
            try:
                if ptype in ("TCP", "SSL", "gRPC"):
                    proxies = proxy_cls.list(project=project_id)
                else:
                    proxies = proxy_cls.list(project=project_id)
                for p in proxies:
                    tp_count += 1
                    certs = ", ".join(p.ssl_certificates) if hasattr(p, "ssl_certificates") and p.ssl_certificates else ""
                    ssl_policy = p.ssl_policy if hasattr(p, "ssl_policy") else ""
                    writer.writerow([
                        p.name,
                        ptype,
                        "Global",
                        p.url_map.split("/")[-1] if p.url_map else "",
                        certs or ssl_policy,
                        p.quic_override if hasattr(p, "quic_override") else "",
                    ])
            except Exception:
                pass
    print(f"  Found {tp_count} target proxies. Report saved to: {tp_csv}")

    # URL maps
    um_csv = f"{project_id}_lb_url_maps_audit.csv"
    um_count = 0
    with open(um_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Region", "Default Service", "Host Rules", "Path Matchers"])
        um_client = compute_v1.UrlMapsClient()
        try:
            for group in um_client.aggregated_list(project=project_id):
                region = group[0].replace("zones/", "").replace("regions/", "")
                for um in group[1].url_maps:
                    um_count += 1
                    host_rules = "; ".join([h.hosts[0] if h.hosts else "" for h in um.host_rules]) if um.host_rules else ""
                    path_matchers = "; ".join([pm.name for pm in um.path_matchers]) if um.path_matchers else ""
                    writer.writerow([
                        um.name,
                        region if region != "global" else "Global",
                        um.default_service.split("/")[-1] if um.default_service else "",
                        host_rules,
                        path_matchers,
                    ])
        except Exception as e:
            print(f"  Error listing URL maps: {e}")
    print(f"  Found {um_count} URL maps. Report saved to: {um_csv}")

    # SSL certificates
    ssl_csv = f"{project_id}_lb_ssl_certificates_audit.csv"
    ssl_count = 0
    with open(ssl_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Type", "Region", "Subject CN", "Subject Alternative Names", "Expire Time", "Issuer"])
        ssl_client = compute_v1.SslCertificatesClient()
        try:
            for group in ssl_client.aggregated_list(project=project_id):
                region = group[0].replace("zones/", "").replace("regions/", "")
                for cert in group[1].ssl_certificates:
                    ssl_count += 1
                    def get_cert_field(obj, *names):
                        for n in names:
                            try:
                                v = getattr(obj, n)
                                if v is not None:
                                    return v
                            except Exception:
                                continue
                        return ""
                    writer.writerow([
                        cert.name,
                        get_cert_field(cert, 'type_', 'type'),
                        region if region != "global" else "Global",
                        get_cert_field(cert, 'subject_common_name', 'subject', 'subjectAlternativeNames'),
                        ", ".join(cert.subject_alternative_names) if get_cert_field(cert, 'subject_alternative_names', 'subjectAlternativeNames') else "",
                        cert.expire_time.strftime("%Y-%m-%d %H:%M:%S") if cert.expire_time else "",
                        get_cert_field(cert, 'issuer', 'Issuer'),
                    ])
        except Exception as e:
            print(f"  Error listing SSL certificates: {e}")
    print(f"  Found {ssl_count} SSL certificates. Report saved to: {ssl_csv}")
    print("Cloud Load Balancing Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_load_balancing(project_input)
