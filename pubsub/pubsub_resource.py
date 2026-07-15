import sys
import os
import csv
import warnings

try:
    from google.cloud import pubsub_v1
except ImportError:
    print("❌ Error: Missing required library. Please run: pip install google-cloud-pubsub")
    sys.exit(1)

# Silence the low-level gRPC C++ logs and Google Auth quota UserWarning
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore", module="google.auth._default")

def extract_name(url):
    return url.split('/')[-1] if url else "Unknown"

def format_duration(duration_obj):
    if not duration_obj:
        return "N/A"
    seconds = getattr(duration_obj, "seconds", 0)
    if seconds == 0:
        return "0s"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    if days > 0:
        return f"{days}d"
    if hours > 0:
        return f"{hours}h"
    return f"{seconds}s"

def audit_pubsub(project_id):
    print(f"\n🚀 Fetching Pub/Sub Resources for project: {project_id}...")
    
    # 1. TOPICS AUDIT
    print(f"\n[1/2] Scanning Pub/Sub Topics...")
    topics_csv = f"{project_id}_pubsub_topics_audit.csv"
    topic_count = 0
    
    try:
        publisher_client = pubsub_v1.PublisherClient()
        project_path = f"projects/{project_id}"
        topics = list(publisher_client.list_topics(request={"project": project_path}))
    except Exception as e:
        print(f"❌ Error fetching Pub/Sub topics (API may be disabled): {e}")
        topics = []

    print(f"\n{'Topic Name':<30} | {'Encryption (CMEK)':<25} | {'Retention':<10} | {'Schema'}")
    print("-" * 85)

    with open(topics_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Topic Name", "KMS Key (CMEK)", "Message Retention", "Schema"])

        for topic in topics:
            topic_count += 1
            name = extract_name(topic.name)
            display_name = name if len(name) <= 30 else name[:27] + "..."
            
            kms_key = topic.kms_key_name if topic.kms_key_name else "Google-Managed"
            display_kms = extract_name(kms_key) if kms_key != "Google-Managed" else kms_key
            if len(display_kms) > 25:
                display_kms = display_kms[:22] + "..."
                
            retention = format_duration(topic.message_retention_duration)
            
            schema = "No Schema"
            if topic.schema_settings and topic.schema_settings.schema:
                schema = extract_name(topic.schema_settings.schema)

            print(f"{display_name:<30} | {display_kms:<25} | {retention:<10} | {schema}")
            writer.writerow([name, kms_key, retention, schema])

    if topic_count == 0 and topics:
        print("No Pub/Sub topics found in this project.")
    print(f"      Found {topic_count} Topics. Report saved to: {topics_csv}")

    # 2. SUBSCRIPTIONS AUDIT
    print(f"\n[2/2] Scanning Pub/Sub Subscriptions...")
    subscriptions_csv = f"{project_id}_pubsub_subscriptions_audit.csv"
    sub_count = 0
    
    try:
        subscriber_client = pubsub_v1.SubscriberClient()
        subscriptions = list(subscriber_client.list_subscriptions(request={"project": project_path}))
    except Exception as e:
        print(f"❌ Error fetching Pub/Sub subscriptions: {e}")
        subscriptions = []

    print(f"\n{'Subscription Name':<30} | {'Topic Name':<25} | {'Ack T/O':<7} | {'Retention':<10} | {'Type':<10} | {'Dead Letter'}")
    print("-" * 105)

    with open(subscriptions_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Subscription Name", "Topic Name", "Ack Deadline (sec)", "Retention", "Subscription Type", "Dead Letter Topic"])

        for sub in subscriptions:
            sub_count += 1
            name = extract_name(sub.name)
            display_name = name if len(name) <= 30 else name[:27] + "..."
            
            topic_name = extract_name(sub.topic)
            display_topic = topic_name if len(topic_name) <= 25 else topic_name[:22] + "..."
            
            ack_deadline = f"{sub.ack_deadline_seconds}s"
            retention = format_duration(sub.message_retention_duration)
            
            # Determine subscription type
            sub_type = "Pull"
            if sub.push_config and sub.push_config.push_endpoint:
                sub_type = "Push"
            elif sub.bigquery_config and sub.bigquery_config.table:
                sub_type = "BigQuery"
            elif sub.cloud_storage_config and sub.cloud_storage_config.bucket:
                sub_type = "GCS"

            dead_letter = "Disabled"
            if sub.dead_letter_policy and sub.dead_letter_policy.dead_letter_topic:
                dead_letter = extract_name(sub.dead_letter_policy.dead_letter_topic)
            display_dl = dead_letter if len(dead_letter) <= 15 else dead_letter[:12] + "..."

            print(f"{display_name:<30} | {display_topic:<25} | {ack_deadline:<7} | {retention:<10} | {sub_type:<10} | {display_dl}")
            writer.writerow([name, topic_name, sub.ack_deadline_seconds, retention, sub_type, dead_letter])

    if sub_count == 0 and subscriptions:
        print("No Pub/Sub subscriptions found in this project.")
    print(f"      Found {sub_count} Subscriptions. Report saved to: {subscriptions_csv}")
    
    print(f"\n✅ Pub/Sub Audit complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        project_input = input("Enter your GCP project ID: ").strip()
        if not project_input:
            print("Project ID cannot be empty.")
            sys.exit(1)
    else:
        project_input = sys.argv[1]

    audit_pubsub(project_input)
