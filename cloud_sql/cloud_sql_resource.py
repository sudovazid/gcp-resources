import csv
import os
import sys
import warnings

try:
    from googleapiclient import discovery
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-api-python-client')
    from googleapiclient import discovery

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_cloud_sql(project_id):
    print(f"Fetching Cloud SQL Instances for project: {project_id}...")

    try:
        # Build the Cloud SQL Admin API client
        client = discovery.build('sqladmin', 'v1beta4', cache_discovery=False)
        request = client.instances().list(project=project_id)
        response = request.execute()
        instances = response.get('items', [])
    except Exception as e:
        err_str = str(e)
        print(f"❌ Error fetching Cloud SQL instances: {err_str}")
        if "403" in err_str or "unauthorized" in err_str.lower() or "permission" in err_str.lower() or "denied" in err_str.lower():
            print(f"   💡 Recommendation: The authenticated identity lacks permission to list Cloud SQL instances.")
            print(f"      Please ensure you have the 'Cloud SQL Viewer' (roles/cloudsql.viewer) or 'Viewer' (roles/viewer) IAM role")
            print(f"      assigned on project '{project_id}'.")
        instances = []

    print(f"\n{'Instance Name':<30} | {'Version':<15} | {'Tier / Size':<20} | {'State':<10} | {'Public IP':<10} | {'Backups'}")
    print("-" * 115)

    csv_file = f"{project_id}_cloudsql_audit.csv"
    count = 0

    with open(csv_file, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Instance Name", "Region", "Database Version", "Tier", "State", "Public IP", "Backups Enabled"])

        if not instances:
            print("No Cloud SQL instances found in this project.")
        else:
            for instance in instances:
                count += 1
                
                name = instance.get('name', 'Unknown')
                display_name = name if len(name) <= 30 else name[:27] + "..."
                region = instance.get('region', 'Unknown')
                
                # Format Database Version
                db_version = instance.get('databaseVersion', 'Unknown')
                if 'POSTGRES' in db_version: 
                    db_version = db_version.replace('POSTGRES_', 'PG_')
                elif 'MYSQL' in db_version: 
                    db_version = db_version.replace('MYSQL_', 'MY_')
                elif 'SQLSERVER' in db_version:
                    db_version = db_version.replace('SQLSERVER_', 'MS_')

                settings = instance.get('settings') or {}
                tier = settings.get('tier', 'Unknown')
                display_tier = tier if len(tier) <= 20 else tier[:17] + "..."
                
                state = instance.get('state', 'Unknown')

                # Security Check: Public IP Address enabled?
                has_public_ip = "No"
                ip_addresses = instance.get('ipAddresses') or []
                for ip in ip_addresses:
                    if ip.get('type') == 'PRIMARY':
                        has_public_ip = "Yes (Risk)"

                # Operational Check: Are automated backups enabled?
                backup_config = settings.get('backupConfiguration') or {}
                backups = "Yes" if backup_config.get('enabled') else "No"

                print(f"{display_name:<30} | {db_version:<15} | {display_tier:<20} | {state:<10} | {has_public_ip:<10} | {backups}")
                writer.writerow([name, region, db_version, tier, state, has_public_ip, backups])

    print(f"\n✅ Cloud SQL Audit complete. {count} instances saved to {csv_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Project ID argument missing.")
        sys.exit(1)

    project_id_arg = sys.argv[1]
    audit_cloud_sql(project_id_arg)
