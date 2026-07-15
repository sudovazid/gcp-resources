import sys
import os
import csv
import warnings

try:
    from google.cloud import functions_v2
except ImportError:
    print("❌ Error: Missing required library. Please run: pip install google-cloud-functions")
    sys.exit(1)

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def audit_functions(project_id):
    print(f"\n🚀 Fetching Cloud Functions (v1 & v2) for project: {project_id}...")
    
    # Initialize GCF Client
    try:
        client = functions_v2.FunctionServiceClient()
        parent = f"projects/{project_id}/locations/-"
        response = client.list_functions(request={"parent": parent})
        functions = list(response)
    except Exception as e:
        print(f"❌ Error fetching Cloud Functions (API may be disabled): {e}")
        functions = []

    # 1. FUNCTIONS AUDIT
    print(f"\n[1/1] Scanning Cloud Functions & Trigger Options...")
    functions_csv = f"{project_id}_cloud_functions_audit.csv"
    function_count = 0
    
    print(f"\n{'Function Name':<30} | {'Region':<15} | {'Gen':<5} | {'State':<10} | {'Runtime':<12} | {'Memory':<8} | {'Public'}")
    print("-" * 95)

    with open(functions_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Function Name", "Location", "Environment (Gen)", "State", "Runtime", "Entry Point", "Available Memory", "Timeout (sec)", "Public Access", "Trigger URL"])

        for fn in functions:
            function_count += 1
            full_name = fn.name
            name = extract_name(full_name)
            
            # Location
            parts = full_name.split('/')
            location = parts[3] if len(parts) > 3 else "Unknown"
            
            # Environment (Gen)
            gen = "v2" if "GEN_2" in str(fn.environment) else "v1"
            
            # State
            state = fn.state.name if hasattr(fn.state, 'name') else str(fn.state)
            state = state.replace('STATE_', '').replace('STATUS_', '')
            
            # Build Config
            runtime = "N/A"
            entry_point = "N/A"
            if fn.build_config:
                runtime = fn.build_config.runtime or "N/A"
                entry_point = fn.build_config.entry_point or "N/A"
                
            # Service Config
            memory = "N/A"
            timeout = 0
            uri = "N/A"
            if fn.service_config:
                memory = fn.service_config.available_memory or "N/A"
                timeout = fn.service_config.timeout_seconds or 0
                uri = fn.service_config.uri or "N/A"
            
            # Public Access check
            public_status = "Private"
            try:
                policy = client.get_iam_policy(request={"resource": full_name})
                is_public = any('allUsers' in binding.members or 'allAuthenticatedUsers' in binding.members 
                                for binding in policy.bindings if 'invoker' in binding.role.lower())
                public_status = "Public!" if is_public else "Private"
            except Exception:
                public_status = "Unknown (No Perms)"

            display_name = name if len(name) <= 30 else name[:27] + "..."
            print(f"{display_name:<30} | {location:<15} | {gen:<5} | {state:<10} | {runtime:<12} | {memory:<8} | {public_status}")
            writer.writerow([name, location, gen, state, runtime, entry_point, memory, timeout, public_status, uri])

    if function_count == 0 and functions:
        print("No Cloud Functions found in this project.")
    print(f"      Found {function_count} Cloud Functions. Report saved to: {functions_csv}")

    print(f"\n✅ Cloud Functions Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_functions(project_input)
