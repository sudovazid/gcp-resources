import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from googleapiclient import discovery
    import google.auth
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-api-python-client google-auth')
    from googleapiclient import discovery
    import google.auth

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def calculate_key_age(valid_after_str):
    if not valid_after_str:
        return "N/A", 0
    # Example format: 2023-08-01T15:30:00Z or 2023-08-01T15:30:00.123Z
    orig_str = valid_after_str
    if valid_after_str.endswith('Z'):
        valid_after_str = valid_after_str[:-1]
    if '.' in valid_after_str:
        valid_after_str = valid_after_str.split('.')[0]
        
    try:
        created_dt = datetime.strptime(valid_after_str, "%Y-%m-%dT%H:%M:%S")
        age_days = (datetime.utcnow() - created_dt).days
        return f"{age_days} days", age_days
    except Exception:
        return "Unknown", 0

def audit_iam(project_id):
    print(f"\n🚀 Fetching IAM & Service Account Resources for: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        iam_client = discovery.build('iam', 'v1', credentials=credentials, cache_discovery=False)
        rm_client = discovery.build('cloudresourcemanager', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing IAM/Resource Manager clients: {e}")
        return

    # 1. SERVICE ACCOUNTS & KEYS AUDIT
    print(f"\n[1/2] Scanning Service Accounts & User-Managed Keys...")
    sa_csv = f"{project_id}_service_accounts_audit.csv"
    keys_csv = f"{project_id}_service_account_keys_audit.csv"
    sa_count = 0
    user_keys_count = 0
    
    try:
        name_path = f"projects/{project_id}"
        request = iam_client.projects().serviceAccounts().list(name=name_path)
        response = request.execute()
        accounts = response.get('accounts', [])
    except Exception as e:
        print(f"❌ Error fetching Service Accounts (API may be disabled): {e}")
        accounts = []

    print(f"\n{'Service Account Email':<50} | {'Status':<10} | {'User Keys':<9}")
    print("-" * 75)

    with open(sa_csv, mode="w", newline="") as sa_file, open(keys_csv, mode="w", newline="") as keys_file:
        sa_writer = csv.writer(sa_file)
        keys_writer = csv.writer(keys_file)
        
        sa_writer.writerow(["Service Account Email", "Unique ID", "Display Name", "Disabled Status"])
        keys_writer.writerow(["Service Account Email", "Key ID", "Key Type", "Created Time", "Age in Days", "Rotation Warning (Age > 90 days)"])

        for sa in accounts:
            sa_count += 1
            email = sa.get('email', 'Unknown')
            display_email = email if len(email) <= 50 else email[:47] + "..."
            unique_id = sa.get('uniqueId', 'N/A')
            display_name = sa.get('displayName', 'N/A')
            disabled = "Disabled" if sa.get('disabled', False) else "Active"
            
            # Fetch keys for this service account
            sa_user_keys = 0
            try:
                keys_request = iam_client.projects().serviceAccounts().keys().list(name=sa['name'])
                keys_response = keys_request.execute()
                keys = keys_response.get('keys', [])
            except Exception:
                keys = []

            for key in keys:
                key_type = key.get('keyType', 'SYSTEM_MANAGED')
                if key_type == 'USER_MANAGED':
                    sa_user_keys += 1
                    user_keys_count += 1
                    key_id = extract_name(key.get('name'))
                    created_time = key.get('validAfterTime', '')
                    age_str, age_days = calculate_key_age(created_time)
                    
                    warning = "Yes (Risk)" if age_days > 90 else "No"
                    keys_writer.writerow([email, key_id, key_type, created_time, age_days, warning])
            
            print(f"{display_email:<50} | {disabled:<10} | {sa_user_keys:<9}")
            sa_writer.writerow([email, unique_id, display_name, disabled])

    if sa_count == 0 and accounts:
        print("No Service Accounts found in this project.")
    print(f"      Evaluated {sa_count} Service Accounts. Found {user_keys_count} user-managed keys.")
    print(f"      Reports saved to: {sa_csv} & {sa_csv.replace('accounts', 'account_keys')}")

    # 2. IAM POLICIES & MEMBERS AUDIT
    print(f"\n[2/2] Scanning Project-Level IAM Roles & Privilege Members...")
    iam_csv = f"{project_id}_iam_policy_audit.csv"
    role_bindings_count = 0
    
    try:
        policy = rm_client.projects().getIamPolicy(resource=project_id, body={}).execute()
        bindings = policy.get('bindings', [])
    except Exception as e:
        print(f"❌ Error fetching IAM Policy: {e}")
        bindings = []

    print(f"\n{'Role':<40} | {'Member Email / Resource':<50} | {'Privilege Level'}")
    print("-" * 110)

    with open(iam_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Role", "Member Type", "Member Email", "High Privilege Level"])

        for binding in bindings:
            role = binding.get('role', 'Unknown')
            members = binding.get('members', [])
            
            # Determine privilege status
            is_high_priv = "Normal"
            role_lower = role.lower()
            if "owner" in role_lower or "admin" in role_lower or "editor" in role_lower:
                is_high_priv = "High (Risk)"

            for member in members:
                role_bindings_count += 1
                
                # Split member string (e.g. user:alice@gmail.com -> user, alice@gmail.com)
                parts = member.split(':', 1)
                m_type = parts[0] if len(parts) > 1 else "Unknown"
                m_email = parts[1] if len(parts) > 1 else member
                
                display_role = role if len(role) <= 40 else role[:37] + "..."
                display_member = m_email if len(m_email) <= 50 else m_email[:47] + "..."
                
                print(f"{display_role:<40} | {display_member:<50} | {is_high_priv}")
                writer.writerow([role, m_type, m_email, is_high_priv])

    if role_bindings_count == 0 and bindings:
        print("No IAM role bindings found for this project.")
    print(f"      Found {role_bindings_count} Member-Role Bindings. Report saved to: {iam_csv}")
    
    print(f"\n✅ IAM & Service Accounts Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_iam(project_input)
