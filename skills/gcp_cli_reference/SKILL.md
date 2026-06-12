---
name: gcp-cli-reference
description: |
  Command syntax reference for the gcp-cli MCP server. Covers 12 GCP services
  with exact gcloud, bq, and gsutil command examples for read, write, and
  destructive operations. Load this skill when using gcp_read, gcp_write,
  or gcp_destructive tools.
---

# GCP CLI Reference Skill

This skill provides exact command syntax for the three gcp-cli MCP tools:

- **`gcp_read`** -- Read-only operations (list, describe, get, show, query with --dry_run)
- **`gcp_write`** -- Mutating operations (create, update, deploy, add-iam-policy-binding)
- **`gcp_destructive`** -- Irreversible operations (delete, remove, destroy, rm). REQUIRES human confirmation.

All commands below omit the CLI prefix (`gcloud`, `bq`, `gsutil`). The MCP server prepends it automatically based on the tool. Pass only the subcommand and flags.

---

## Mandatory Rules

1. Always specify `--project=PROJECT_ID` for cross-project clarity.
2. Always specify `--region=REGION` for regional resources (Cloud Run, Compute, etc.).
3. Always use `--format=json` for machine-readable output. The server auto-appends this flag, but including it explicitly is good practice.
4. NEVER run destructive commands without confirming the target resource first via a read operation.
5. Use `--quiet` on write and destructive commands to suppress interactive prompts (the MCP server is non-interactive).

---

## 1. Cloud Run

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List services | `gcp_read` | `run services list --project=PROJECT_ID --region=REGION` |
| Describe service | `gcp_read` | `run services describe SERVICE_NAME --project=PROJECT_ID --region=REGION` |
| List revisions | `gcp_read` | `run revisions list --service=SERVICE_NAME --project=PROJECT_ID --region=REGION` |
| Describe revision | `gcp_read` | `run revisions describe REVISION_NAME --project=PROJECT_ID --region=REGION` |
| Deploy service | `gcp_write` | `run deploy SERVICE_NAME --image=IMAGE_URL --project=PROJECT_ID --region=REGION --quiet` |
| Update traffic | `gcp_write` | `run services update-traffic SERVICE_NAME --to-revisions=REVISION=PERCENT --project=PROJECT_ID --region=REGION` |
| Delete service | `gcp_destructive` | `run services delete SERVICE_NAME --project=PROJECT_ID --region=REGION --quiet` |

---

## 2. IAM and Service Accounts

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List service accounts | `gcp_read` | `iam service-accounts list --project=PROJECT_ID` |
| Describe service account | `gcp_read` | `iam service-accounts describe SA_EMAIL --project=PROJECT_ID` |
| Get IAM policy | `gcp_read` | `projects get-iam-policy PROJECT_ID` |
| Create service account | `gcp_write` | `iam service-accounts create SA_NAME --display-name="DISPLAY_NAME" --project=PROJECT_ID` |
| Add IAM policy binding | `gcp_write` | `projects add-iam-policy-binding PROJECT_ID --member=serviceAccount:SA_EMAIL --role=ROLE` |
| List SA keys | `gcp_read` | `iam service-accounts keys list --iam-account=SA_EMAIL --project=PROJECT_ID` |
| Create SA key | `gcp_write` | `iam service-accounts keys create KEY_FILE.json --iam-account=SA_EMAIL --project=PROJECT_ID` |
| Remove IAM policy binding | `gcp_destructive` | `projects remove-iam-policy-binding PROJECT_ID --member=serviceAccount:SA_EMAIL --role=ROLE` |
| Delete service account | `gcp_destructive` | `iam service-accounts delete SA_EMAIL --project=PROJECT_ID --quiet` |
| Delete SA key | `gcp_destructive` | `iam service-accounts keys delete KEY_ID --iam-account=SA_EMAIL --project=PROJECT_ID --quiet` |

### Service Account Best Practices

- PREFER custom roles over predefined broad roles (e.g., `roles/editor`).
- Use `roles/iam.serviceAccountTokenCreator` sparingly -- it grants impersonation capability.
- Document key rotation schedule. Keys SHOULD be rotated every 90 days.
- PREFER Workload Identity Federation over exported key files for workloads running on GCP.
- ALWAYS audit existing bindings with `get-iam-policy` before adding new ones.

---

## 3. Secret Manager

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List secrets | `gcp_read` | `secrets list --project=PROJECT_ID` |
| Describe secret | `gcp_read` | `secrets describe SECRET_ID --project=PROJECT_ID` |
| List secret versions | `gcp_read` | `secrets versions list SECRET_ID --project=PROJECT_ID` |
| Access secret version | `gcp_read` | `secrets versions access VERSION --secret=SECRET_ID --project=PROJECT_ID` |
| Create secret | `gcp_write` | `secrets create SECRET_ID --replication-policy=automatic --project=PROJECT_ID` |
| Add secret version | `gcp_write` | `secrets versions add SECRET_ID --data-file=FILE_PATH --project=PROJECT_ID` |
| Delete secret | `gcp_destructive` | `secrets delete SECRET_ID --project=PROJECT_ID --quiet` |
| Destroy secret version | `gcp_destructive` | `secrets versions destroy VERSION --secret=SECRET_ID --project=PROJECT_ID --quiet` |

---

## 4. Cloud Storage (Buckets)

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List buckets | `gcp_read` | `storage buckets list --project=PROJECT_ID` |
| Describe bucket | `gcp_read` | `storage buckets describe gs://BUCKET_NAME` |
| Create bucket | `gcp_write` | `storage buckets create gs://BUCKET_NAME --project=PROJECT_ID --location=LOCATION --uniform-bucket-level-access` |
| Update bucket | `gcp_write` | `storage buckets update gs://BUCKET_NAME --versioning --project=PROJECT_ID` |
| Delete bucket | `gcp_destructive` | `storage buckets delete gs://BUCKET_NAME --project=PROJECT_ID --quiet` |

### Cloud Storage Best Practices

- Use `gcloud storage` (NOT `gsutil`) for all new projects. `gsutil` is legacy.
- ALWAYS specify `--location` when creating buckets.
- Use `--uniform-bucket-level-access` to enforce IAM-only access control.
- Use `--recursive` flag explicitly when needed for object operations.
- Verify bucket contents with a read operation before deleting a bucket.

---

## 5. Cloud Storage (Objects)

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List objects | `gcp_read` | `storage ls gs://BUCKET_NAME/PREFIX` |
| Read object content | `gcp_read` | `storage cat gs://BUCKET_NAME/OBJECT_PATH` |
| Upload object | `gcp_write` | `storage cp LOCAL_PATH gs://BUCKET_NAME/DESTINATION_PATH` |
| Download object | `gcp_read` | `storage cp gs://BUCKET_NAME/OBJECT_PATH LOCAL_PATH` |
| Move/rename object | `gcp_write` | `storage mv gs://BUCKET_NAME/SRC_PATH gs://BUCKET_NAME/DST_PATH` |
| Copy between buckets | `gcp_write` | `storage cp gs://SRC_BUCKET/PATH gs://DST_BUCKET/PATH` |
| Delete object | `gcp_destructive` | `storage rm gs://BUCKET_NAME/OBJECT_PATH` |
| Delete objects recursively | `gcp_destructive` | `storage rm gs://BUCKET_NAME/PREFIX --recursive` |

---

## 6. Cloud Logging

| Operation | Tool | Command |
| :--- | :--- | :--- |
| Read logs | `gcp_read` | `logging read "FILTER" --project=PROJECT_ID --limit=50 --freshness=1d` |
| Read logs (resource filter) | `gcp_read` | `logging read "resource.type=cloud_run_revision AND severity>=ERROR" --project=PROJECT_ID --limit=50` |
| List log sinks | `gcp_read` | `logging sinks list --project=PROJECT_ID` |
| Describe log sink | `gcp_read` | `logging sinks describe SINK_NAME --project=PROJECT_ID` |
| List log metrics | `gcp_read` | `logging metrics list --project=PROJECT_ID` |
| Create log sink | `gcp_write` | `logging sinks create SINK_NAME DESTINATION --log-filter="FILTER" --project=PROJECT_ID` |
| Update log sink | `gcp_write` | `logging sinks update SINK_NAME --log-filter="NEW_FILTER" --project=PROJECT_ID` |
| Create log metric | `gcp_write` | `logging metrics create METRIC_NAME --description="DESC" --log-filter="FILTER" --project=PROJECT_ID` |
| Delete log sink | `gcp_destructive` | `logging sinks delete SINK_NAME --project=PROJECT_ID --quiet` |
| Delete log metric | `gcp_destructive` | `logging metrics delete METRIC_NAME --project=PROJECT_ID --quiet` |

Common log filters:

```
resource.type="cloud_run_revision" AND severity>=ERROR
resource.type="gce_instance" AND logName="projects/PROJECT_ID/logs/syslog"
timestamp>="2024-01-01T00:00:00Z" AND timestamp<="2024-01-02T00:00:00Z"
textPayload:"error message substring"
```

---

## 7. BigQuery

BigQuery uses the `bq` CLI. Commands below use `bq` subcommand syntax.

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List datasets | `gcp_read` | `bq ls --project_id=PROJECT_ID` |
| List tables in dataset | `gcp_read` | `bq ls PROJECT_ID:DATASET_ID` |
| Show table schema | `gcp_read` | `bq show --schema PROJECT_ID:DATASET_ID.TABLE_ID` |
| Show table details | `gcp_read` | `bq show PROJECT_ID:DATASET_ID.TABLE_ID` |
| Dry run query (cost est.) | `gcp_read` | `bq query --use_legacy_sql=false --dry_run "SELECT * FROM \`PROJECT_ID.DATASET_ID.TABLE_ID\` LIMIT 100"` |
| Run query | `gcp_read` | `bq query --use_legacy_sql=false --max_rows=100 "SELECT col1, col2 FROM \`PROJECT_ID.DATASET_ID.TABLE_ID\` WHERE condition LIMIT 100"` |
| Create dataset | `gcp_write` | `bq mk --dataset --location=LOCATION PROJECT_ID:DATASET_ID` |
| Create table | `gcp_write` | `bq mk --table PROJECT_ID:DATASET_ID.TABLE_ID SCHEMA` |
| Load data | `gcp_write` | `bq load --source_format=CSV PROJECT_ID:DATASET_ID.TABLE_ID gs://BUCKET/FILE.csv SCHEMA` |
| Copy table | `gcp_write` | `bq cp PROJECT_ID:SRC_DATASET.SRC_TABLE PROJECT_ID:DST_DATASET.DST_TABLE` |
| Remove table | `gcp_destructive` | `bq rm --table PROJECT_ID:DATASET_ID.TABLE_ID` |
| Remove dataset | `gcp_destructive` | `bq rm --recursive --dataset PROJECT_ID:DATASET_ID` |

### BigQuery Safety

- ALWAYS use `--use_legacy_sql=false`. Standard SQL is REQUIRED.
- ALWAYS run `bq query --dry_run` before executing real queries to estimate cost.
- Use `--max_rows=100` to limit output and prevent overwhelming responses.
- Include `_PARTITIONTIME` filters on partitioned tables to avoid full-table scans.
- NEVER run `bq rm --recursive` on a dataset without confirming contents first.
- Prefer `LIMIT` clauses in all exploratory queries.

---

## 8. Pub/Sub

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List topics | `gcp_read` | `pubsub topics list --project=PROJECT_ID` |
| Describe topic | `gcp_read` | `pubsub topics describe TOPIC_NAME --project=PROJECT_ID` |
| List subscriptions | `gcp_read` | `pubsub subscriptions list --project=PROJECT_ID` |
| Describe subscription | `gcp_read` | `pubsub subscriptions describe SUBSCRIPTION_NAME --project=PROJECT_ID` |
| Create topic | `gcp_write` | `pubsub topics create TOPIC_NAME --project=PROJECT_ID` |
| Publish message | `gcp_write` | `pubsub topics publish TOPIC_NAME --message="MESSAGE_BODY" --project=PROJECT_ID` |
| Create subscription | `gcp_write` | `pubsub subscriptions create SUBSCRIPTION_NAME --topic=TOPIC_NAME --project=PROJECT_ID` |
| Delete topic | `gcp_destructive` | `pubsub topics delete TOPIC_NAME --project=PROJECT_ID --quiet` |
| Delete subscription | `gcp_destructive` | `pubsub subscriptions delete SUBSCRIPTION_NAME --project=PROJECT_ID --quiet` |

---

## 9. Firestore

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List databases | `gcp_read` | `firestore databases list --project=PROJECT_ID` |
| Describe database | `gcp_read` | `firestore databases describe --database=DATABASE_ID --project=PROJECT_ID` |
| List indexes | `gcp_read` | `firestore indexes composite list --database=DATABASE_ID --project=PROJECT_ID` |
| Create database | `gcp_write` | `firestore databases create --database=DATABASE_ID --location=LOCATION --type=firestore-native --project=PROJECT_ID` |
| Create composite index | `gcp_write` | `firestore indexes composite create --database=DATABASE_ID --collection-group=COLLECTION --field-config=FIELD_CONFIG --project=PROJECT_ID` |
| Export data | `gcp_write` | `firestore export gs://BUCKET_NAME/EXPORT_PREFIX --database=DATABASE_ID --project=PROJECT_ID` |
| Delete database | `gcp_destructive` | `firestore databases delete --database=DATABASE_ID --project=PROJECT_ID --quiet` |
| Delete index | `gcp_destructive` | `firestore indexes composite delete INDEX_ID --database=DATABASE_ID --project=PROJECT_ID --quiet` |

---

## 10. API Services

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List enabled services | `gcp_read` | `services list --enabled --project=PROJECT_ID` |
| List available services | `gcp_read` | `services list --available --project=PROJECT_ID` |
| Check if service is enabled | `gcp_read` | `services list --enabled --filter="config.name:SERVICE_NAME" --project=PROJECT_ID` |
| Enable API | `gcp_write` | `services enable SERVICE_NAME --project=PROJECT_ID` |
| Disable API | `gcp_destructive` | `services disable SERVICE_NAME --project=PROJECT_ID --quiet` |

Common service names:

```
run.googleapis.com              -- Cloud Run
cloudfunctions.googleapis.com   -- Cloud Functions
secretmanager.googleapis.com    -- Secret Manager
firestore.googleapis.com        -- Firestore
pubsub.googleapis.com           -- Pub/Sub
bigquery.googleapis.com         -- BigQuery
logging.googleapis.com          -- Cloud Logging
iam.googleapis.com              -- IAM
storage.googleapis.com          -- Cloud Storage
compute.googleapis.com          -- Compute Engine
```

---

## 11. Compute / VMs

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List instances | `gcp_read` | `compute instances list --project=PROJECT_ID` |
| Describe instance | `gcp_read` | `compute instances describe INSTANCE_NAME --zone=ZONE --project=PROJECT_ID` |
| List zones | `gcp_read` | `compute zones list --project=PROJECT_ID` |
| List regions | `gcp_read` | `compute regions list --project=PROJECT_ID` |
| List machine types | `gcp_read` | `compute machine-types list --zones=ZONE --project=PROJECT_ID` |
| Create instance | `gcp_write` | `compute instances create INSTANCE_NAME --zone=ZONE --machine-type=MACHINE_TYPE --image-family=IMAGE_FAMILY --image-project=IMAGE_PROJECT --project=PROJECT_ID` |
| Start instance | `gcp_write` | `compute instances start INSTANCE_NAME --zone=ZONE --project=PROJECT_ID` |
| Stop instance | `gcp_write` | `compute instances stop INSTANCE_NAME --zone=ZONE --project=PROJECT_ID` |
| Delete instance | `gcp_destructive` | `compute instances delete INSTANCE_NAME --zone=ZONE --project=PROJECT_ID --quiet` |

---

## 12. Projects and Config

| Operation | Tool | Command |
| :--- | :--- | :--- |
| List projects | `gcp_read` | `projects list` |
| Describe project | `gcp_read` | `projects describe PROJECT_ID` |
| Get current config | `gcp_read` | `config list` |
| Get specific config value | `gcp_read` | `config get-value project` |
| Get current account | `gcp_read` | `config get-value account` |
| Set project | `gcp_write` | `config set project PROJECT_ID` |
| Set region | `gcp_write` | `config set run/region REGION` |
| Set zone | `gcp_write` | `config set compute/zone ZONE` |
| Unset config value | `gcp_write` | `config unset project` |

---

## Tool Routing Summary

Use this quick-reference to determine which MCP tool to use:

| Action Verb | Tool | Examples |
| :--- | :--- | :--- |
| list, describe, get, show, read, ls, cat, query --dry_run | `gcp_read` | Inspect resources, estimate costs |
| create, deploy, update, add, enable, set, cp, mv, publish, load, mk | `gcp_write` | Provision resources, modify config |
| delete, remove, disable, destroy, rm | `gcp_destructive` | Remove resources permanently |

IMPORTANT: When in doubt, use `gcp_read` first to verify the resource exists and inspect its state before running any write or destructive operation.
