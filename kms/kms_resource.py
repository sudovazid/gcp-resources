import sys
import os
import csv
import warnings

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

def extract_location_and_keyring(resource_path):
    # Format: projects/{project_id}/locations/{location}/keyRings/{key_ring_id}
    parts = resource_path.split('/')
    if len(parts) >= 6:
        return parts[3], parts[5]
    return "Unknown", resource_path.split('/')[-1] if resource_path else "Unknown"

def extract_key_name(resource_path):
    # Format: projects/{project_id}/locations/{location}/keyRings/{key_ring_id}/cryptoKeys/{key_id}
    return resource_path.split('/')[-1] if resource_path else "Unknown"

def format_duration(seconds_str):
    if not seconds_str:
        return "None"
    try:
        # e.g., "7776000s" -> "90 days"
        seconds = int(seconds_str.rstrip('s'))
        days = seconds // 86400
        if days > 0:
            return f"{days}d"
        hours = seconds // 3600
        return f"{hours}h"
    except Exception:
        return seconds_str

def audit_kms(project_id):
    print(f"\n🚀 Fetching Cloud KMS Resources for project: {project_id}...")
    
    try:
        credentials, _ = google.auth.default()
        client = discovery.build('cloudkms', 'v1', credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"❌ Error initializing Cloud KMS client: {e}")
        return

    parent = f"projects/{project_id}/locations/-"
    key_rings_csv = f"{project_id}_kms_key_rings_audit.csv"
    crypto_keys_csv = f"{project_id}_kms_crypto_keys_audit.csv"
    
    key_rings_list = []
    crypto_keys_list = []

    # 1. SCAN KEY RINGS
    print(f"\n[1/2] Scanning KMS Key Rings...")
    try:
        request = client.projects().locations().keyRings().list(parent=parent)
        while request is not None:
            response = request.execute()
            key_rings_list.extend(response.get('keyRings', []))
            request = client.projects().locations().keyRings().list_next(request, response)
    except Exception as e:
        print(f"⚠️ Error or access denied listing Key Rings: {e}")

    print(f"\n{'Key Ring ID':<25} | {'Location':<15} | {'Full Resource Path'}")
    print("-" * 95)

    with open(key_rings_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Key Ring ID", "Location", "Resource Path"])

        for ring in key_rings_list:
            name_path = ring.get('name', '')
            loc, ring_id = extract_location_and_keyring(name_path)
            
            display_ring = ring_id if len(ring_id) <= 25 else ring_id[:22] + "..."
            print(f"{display_ring:<25} | {loc:<15} | {name_path}")
            writer.writerow([ring_id, loc, name_path])

    print(f"      Found {len(key_rings_list)} Key Rings. Report saved to: {key_rings_csv}")

    # 2. SCAN CRYPTO KEYS
    print(f"\n[2/2] Scanning Cryptographic Keys in each Key Ring...")
    for ring in key_rings_list:
        ring_name = ring.get('name', '')
        _, ring_id = extract_location_and_keyring(ring_name)
        
        try:
            request = client.projects().locations().keyRings().cryptoKeys().list(parent=ring_name)
            while request is not None:
                response = request.execute()
                crypto_keys_list.extend(response.get('cryptoKeys', []))
                request = client.projects().locations().keyRings().cryptoKeys().list_next(request, response)
        except Exception as e:
            print(f"⚠️ Error listing CryptoKeys inside Key Ring '{ring_id}': {e}")

    print(f"\n{'Key ID':<25} | {'Purpose':<20} | {'Primary State':<15} | {'Rotation':<10} | {'Algorithm'}")
    print("-" * 95)

    with open(crypto_keys_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Key ID", "Key Ring ID", "Purpose", "Primary Version State", "Rotation Period", "Next Rotation Time", "Algorithm"])

        for key in crypto_keys_list:
            name_path = key.get('name', '')
            key_id = extract_key_name(name_path)
            
            # Extract ring ID from name path
            # Format: projects/{project_id}/locations/{location}/keyRings/{key_ring_id}/cryptoKeys/{key_id}
            parts = name_path.split('/')
            ring_id = parts[5] if len(parts) >= 6 else "Unknown"
            
            purpose = key.get('purpose', 'Unknown')
            rotation_period = format_duration(key.get('rotationPeriod', ''))
            next_rotation = key.get('nextRotationTime', 'None')
            
            primary = key.get('primary', {})
            primary_state = primary.get('state', 'N/A')
            algorithm = primary.get('algorithm', 'N/A')

            display_key = key_id if len(key_id) <= 25 else key_id[:22] + "..."
            display_purpose = purpose if len(purpose) <= 20 else purpose[:17] + "..."
            display_state = primary_state if len(primary_state) <= 15 else primary_state[:12] + "..."
            display_alg = algorithm if len(algorithm) <= 20 else algorithm[:17] + "..."
            
            print(f"{display_key:<25} | {display_purpose:<20} | {display_state:<15} | {rotation_period:<10} | {display_alg}")
            writer.writerow([key_id, ring_id, purpose, primary_state, rotation_period, next_rotation, algorithm])

    print(f"      Found {len(crypto_keys_list)} Cryptographic Keys. Report saved to: {crypto_keys_csv}")
    print(f"\n✅ Cloud KMS Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_kms(project_input)
