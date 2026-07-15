import sys
import os
import csv
import warnings

try:
    from googleapiclient import discovery
    import google.auth
except ImportError:
    print("❌ Error: Missing required libraries. Please run: pip install google-api-python-client google-auth")
    sys.exit(1)

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(resource_path):
    return resource_path.split('/')[-1] if resource_path else "Unknown"

def get_organization_id(project_id):
    try:
        credentials, _ = google.auth.default()
        crm_client = discovery.build('cloudresourcemanager', 'v3', credentials=credentials, cache_discovery=False)
        project = crm_client.projects().get(name=f"projects/{project_id}").execute()
        parent = project.get('parent', '') # Format: "organizations/123" or "folders/456"
        
        while parent:
            if parent.startswith('organizations/'):
                return parent.split('/')[-1]
            elif parent.startswith('folders/'):
                folder = crm_client.folders().get(name=parent).execute()
                parent = folder.get('parent', '')
            else:
                break
    except Exception as e:
        print(f"⚠️ Could not retrieve organization parent for project: {e}")
    return None

def audit_vpc_sc(project_id):
    print(f"\n🚀 Fetching VPC Service Controls for project: {project_id}...")
    
    org_id = get_organization_id(project_id)
    if not org_id:
        print("❌ Error: VPC Service Controls require an organization context. Could not resolve organization ID.")
        return

    print(f"🏢 Resolved parent Organization ID: {org_id}")

    try:
        credentials, _ = google.auth.default()
        acm_client = discovery.build('accesscontextmanager', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Access Context Manager client: {e}")
        return

    vpc_sc_csv = f"{project_id}_vpc_sc_perimeters_audit.csv"
    perimeters_list = []

    # 1. LIST ACCESS POLICIES
    print(f"\n[1/2] Scanning Access Policies in Organization...")
    policies = []
    try:
        policies_response = acm_client.accessPolicies().list(parent=f"organizations/{org_id}").execute()
        policies = policies_response.get('accessPolicies', [])
    except Exception as e:
        print(f"❌ Error listing Access Policies: {e}")
        print("💡 Hint: Ensure the Access Context Manager API is enabled and your credentials have organization-level Viewer/Admin roles.")
        return

    if not policies:
        print("⚠️ No Access Policies found in this organization.")
        return

    # 2. LIST SERVICE PERIMETERS
    print(f"\n[2/2] Scanning Service Perimeters...")
    for policy in policies:
        policy_name = policy.get('name', '')
        policy_title = policy.get('title', 'Unnamed Policy')
        
        try:
            perimeters_response = acm_client.accessPolicies().servicePerimeters().list(parent=policy_name).execute()
            policy_perimeters = perimeters_response.get('servicePerimeters', [])
            for p in policy_perimeters:
                p['_policy_title'] = policy_title
                perimeters_list.append(p)
        except Exception as e:
            print(f"⚠️ Error listing Service Perimeters for policy '{policy_title}': {e}")

    print(f"\n{'Perimeter Name':<25} | {'Policy':<15} | {'Type':<18} | {'Protected Projects':<20} | {'Restricted Services'}")
    print("-" * 110)

    with open(vpc_sc_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Perimeter Name", "Policy Title", "Perimeter Type", "Enforced Projects", "Enforced Services", "Dry-Run Projects", "Dry-Run Services"])

        for perimeter in perimeters_list:
            title = perimeter.get('title', 'Unknown')
            policy_title = perimeter.get('_policy_title', 'Unknown')
            p_type = perimeter.get('perimeterType', 'PERIMETER_TYPE_REGULAR')
            
            # Enforced configuration (status)
            status = perimeter.get('status', {})
            enforced_projects = status.get('resources', [])
            enforced_services = status.get('restrictedServices', [])
            
            # Dry-run configuration (spec)
            spec = perimeter.get('spec', {})
            dry_run_projects = spec.get('resources', [])
            dry_run_services = spec.get('restrictedServices', [])
            
            # For display, show count or slice
            display_projects_count = len(enforced_projects)
            display_services_count = len(enforced_services)
            
            display_title = title if len(title) <= 25 else title[:22] + "..."
            display_policy = policy_title if len(policy_title) <= 15 else policy_title[:12] + "..."
            display_type = p_type.replace('PERIMETER_TYPE_', '')
            
            print(f"{display_title:<25} | {display_policy:<15} | {display_type:<18} | {f'{display_projects_count} projects':<20} | {display_services_count} services")
            
            writer.writerow([
                title, 
                policy_title, 
                p_type, 
                ", ".join(enforced_projects), 
                ", ".join(enforced_services),
                ", ".join(dry_run_projects),
                ", ".join(dry_run_services)
            ])

    print(f"\n      Found {len(perimeters_list)} Service Perimeters. Report saved to: {vpc_sc_csv}")
    print(f"\n✅ VPC Service Controls Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_vpc_sc(project_input)
