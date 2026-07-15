import sys
import os
import csv
import warnings
from datetime import datetime

try:
    from google.cloud import binaryauthorization_v1
    from google.api_core import exceptions
except ImportError:
    from utils.install_helper import prompt_install
    prompt_install('google-cloud-binary-authorization')
    from google.cloud import binaryauthorization_v1
    from google.api_core import exceptions

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def audit_binauthz(project_id):
    print(f"\nFetching Binary Authorization Resources for project: {project_id}...")
    client = binaryauthorization_v1.BinauthzManagementServiceV1Client()

    # Policy
    pol_csv = f"{project_id}_binauthz_policy_audit.csv"
    policy = None
    try:
        policy = client.get_policy(name=f"projects/{project_id}/policy")
    except Exception as e:
        print(f"  Error fetching policy: {e}")

    with open(pol_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Policy Name", "Global Policy Evaluation Mode", "Cluster Admission Rules", "Default Admission Rule"])
        if policy:
            def_rules = ""
            if policy.default_admission_rule:
                dr = policy.default_admission_rule
                def_rules = f"EvalMode={dr.evaluation_mode.name if hasattr(dr.evaluation_mode, 'name') else dr.evaluation_mode}, EnforceMode={dr.enforcement_mode.name if hasattr(dr.enforcement_mode, 'name') else dr.enforcement_mode}"
            cluster_rules = ""
            if policy.cluster_admission_rules:
                cluster_rules = "; ".join([f"{k}:{v.evaluation_mode.name if hasattr(v.evaluation_mode, 'name') else v.evaluation_mode}" for k, v in policy.cluster_admission_rules.items()])
            writer.writerow([
                policy.name,
                policy.global_policy_evaluation_mode.name if hasattr(policy, "global_policy_evaluation_mode") and hasattr(policy.global_policy_evaluation_mode, "name") else "",
                cluster_rules,
                def_rules,
            ])
            print(f"  Policy: {policy.name}")
        else:
            writer.writerow(["N/A", "", "", ""])
    print(f"  Policy report saved to: {pol_csv}")

    # Attestors
    att_csv = f"{project_id}_binauthz_attestors_audit.csv"
    att_count = 0
    with open(att_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Attestor Name", "Description", "Note Reference", "Public Key IDs", "Create Time", "Update Time"])
        try:
            attestors = list(client.list_attestors(parent=f"projects/{project_id}"))
            for att in attestors:
                att_count += 1
                pk_ids = []
                if att.user_owned_grafeas_note and att.user_owned_grafeas_note.public_keys:
                    for pk in att.user_owned_grafeas_note.public_keys:
                        pk_ids.append(pk.id)
                writer.writerow([
                    att.name.split("/")[-1],
                    att.description,
                    att.user_owned_grafeas_note.note_reference if att.user_owned_grafeas_note else "",
                    ", ".join(pk_ids),
                    att.create_time.strftime("%Y-%m-%d %H:%M:%S") if att.create_time else "",
                    att.update_time.strftime("%Y-%m-%d %H:%M:%S") if att.update_time else "",
                ])
                print(f"  Attestor: {att.name.split('/')[-1]}")
        except Exception as e:
            print(f"  Error listing attestors: {e}")
    print(f"  Found {att_count} attestors. Report saved to: {att_csv}")
    print("Binary Authorization Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
    else:
        project_input = sys.argv[1]
    audit_binauthz(project_input)
