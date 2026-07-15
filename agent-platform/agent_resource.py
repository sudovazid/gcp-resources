import os
import sys
import warnings
import csv
from google.cloud import dialogflowcx_v3

# 1. Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def get_dialogflow_agents(project_id):
    print(f"\n1. Fetching Dialogflow CX Agents for project: {project_id}...")
    print("   (Scanning regions, this might take a few seconds...)")
    
    # Common Dialogflow CX regions. Add or remove as needed for your organization.
    locations = [
        'global', 'us-central1', 'us-east1', 'us-west1', 
        'europe-west1', 'europe-west2', 'asia-northeast1', 'australia-southeast1'
    ]
    
    agents_found = []

    for loc in locations:
        # Dialogflow requires a region-specific endpoint if it's not 'global'
        client_options = {"api_endpoint": f"{loc}-dialogflow.googleapis.com"} if loc != 'global' else {}
        client = dialogflowcx_v3.AgentsClient(client_options=client_options)
        
        parent = f"projects/{project_id}/locations/{loc}"
        
        try:
            request = dialogflowcx_v3.ListAgentsRequest(parent=parent)
            # Timeout ensures we don't hang too long on regions you don't use
            results = client.list_agents(request=request, timeout=5)
            
            for agent in results:
                agents_found.append({
                    "name": agent.display_name,
                    "location": loc,
                    "language": agent.default_language_code,
                    "timezone": agent.time_zone,
                    "description": agent.description or "N/A"
                })
        except Exception:
            # If the API isn't enabled in a region, or access is denied, we skip it
            continue

    # Setup the console table header
    print(f"\n{'Agent Name':<35} | {'Location':<15} | {'Lang':<6} | {'Time Zone':<20} | {'Description'}")
    print("-" * 110)

    csv_filename = f"{project_id}_dialogflow_agents.csv"

    with open(csv_filename, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Agent Name", "Location", "Language", "Time Zone", "Description"])

        for agent in agents_found:
            name = agent["name"]
            display_name = name if len(name) <= 35 else name[:32] + "..."
            
            # 1. Print to Terminal
            print(f"{display_name:<35} | {agent['location']:<15} | {agent['language']:<6} | {agent['timezone']:<20} | {agent['description']}")
            
            # 2. Write to CSV
            writer.writerow([name, agent["location"], agent["language"], agent["timezone"], agent["description"]])

    if not agents_found:
        print("No Dialogflow CX Agents found in the scanned regions.")
    else:
        print(f"\n✅ Success! Evaluated {len(agents_found)} agents. Data exported to: {csv_filename}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_input = sys.argv[1]
    else:
        project_input = input("Enter your GCP project ID: ").strip()

    if project_input:
        get_dialogflow_agents(project_input)
    else:
        print("Project ID cannot be empty.")
        sys.exit(1)
