terraform {
  required_version = ">= 0.14"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

# Abilita le API necessarie
resource "google_project_service" "servicenetworking" {
  service = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "sqladmin" {
  service = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "run" {
  service = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "vpcaccess" {
  service = "vpcaccess.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "pubsub" {
  service = "pubsub.googleapis.com"
  disable_on_destroy = false
}

# VPC Connector per Cloud Run
resource "google_vpc_access_connector" "connector" {
  name          = "vpc-connector"
  ip_cidr_range = "10.8.0.0/28"
  network       = var.vpc_network
  region        = var.region

  depends_on = [google_project_service.vpcaccess]
}

# VPC Peering per Cloud SQL Private IP
resource "google_compute_global_address" "private_ip_address" {
  name          = "sql-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = var.vpc_network

  depends_on = [google_project_service.servicenetworking]
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = var.vpc_network
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]

  depends_on = [
    google_compute_global_address.private_ip_address,
    google_project_service.servicenetworking
  ]
}

# Bucket per file CSV
resource "google_storage_bucket" "csv_bucket" {
  name                        = "${var.project}-csv-bucket"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# Cloud SQL (PostgreSQL)
resource "google_sql_database_instance" "main_db" {
  name             = "${var.project}-db"
  region           = var.region
  database_version = "POSTGRES_14"
  deletion_protection = false

  settings {
    tier = "db-f1-micro"
    ip_configuration {
      ipv4_enabled    = false
      private_network = var.vpc_network
    }
  }

  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.sqladmin
  ]
}

resource "google_sql_database" "db" {
  name     = "appdb"
  instance = google_sql_database_instance.main_db.name
}

resource "google_sql_user" "users" {
  name     = "appuser"
  instance = google_sql_database_instance.main_db.name
  password = var.db_password
}

# Service Accounts
resource "google_service_account" "orchestratore_service_account" {
  account_id   = "anonidata-orchestratore"
  display_name = "AnoniData Orchestratore Service Account"
}

resource "google_service_account" "frontend_service_account" {
  account_id   = "anonidata-frontend"
  display_name = "AnoniData Frontend Service Account"
}

resource "google_service_account" "anonymizer_service_account" {
  account_id   = "anonidata-anonymizer"
  display_name = "AnoniData Anonymizer Service Account"
}

resource "google_service_account" "formatter_service_account" {
  account_id   = "anonidata-formatter"
  display_name = "AnoniData Formatter Service Account"
}

# IAM per orchestratore (pubsub, storage, cloudsql, job execution)
resource "google_project_iam_member" "orchestratore_pubsub_publisher" {
  project = var.project
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.orchestratore_service_account.email}"
}

resource "google_project_iam_member" "orchestratore_pubsub_subscriber" {
  project = var.project
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.orchestratore_service_account.email}"
}

resource "google_project_iam_member" "orchestratore_storage" {
  project = var.project
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.orchestratore_service_account.email}"
}

resource "google_project_iam_member" "orchestratore_cloudsql" {
  project = var.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.orchestratore_service_account.email}"
}

# DA RIMUOVERE DA GCR 
resource "google_project_iam_member" "orchestratore_run_invoker" {
  project = var.project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.orchestratore_service_account.email}"
}

# IAM per formatter (pubsub)
resource "google_project_iam_member" "formatter_pubsub_publisher" {
  project = var.project
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.formatter_service_account.email}"
}

resource "google_project_iam_member" "formatter_pubsub_subscriber" {
  project = var.project
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.formatter_service_account.email}"
}

# IAM per anonymizer (pubsub)
resource "google_project_iam_member" "anonymizer_pubsub_publisher" {
  project = var.project
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.anonymizer_service_account.email}"
}

resource "google_project_iam_member" "anonymizer_pubsub_subscriber" {
  project = var.project
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.anonymizer_service_account.email}"
}

# IAM per frontend (solo invocazione orchestratore)
resource "google_project_iam_member" "frontend_run_invoker" {
  project = var.project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.frontend_service_account.email}"
}

resource "google_cloud_run_service_iam_member" "formatter_invoker" {
  service  = google_cloud_run_v2_service.formatter.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.formatter_service_account.email}"
}

resource "google_cloud_run_service_iam_member" "anonymizer_invoker" {
  service  = google_cloud_run_v2_service.anonymizer.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.anonymizer_service_account.email}"
}

# === Pub/Sub Topics e Subscription per orchestrazione servizi ===

# Orchestratore -> Formatter
resource "google_pubsub_topic" "formatter_input" {
  name = "formatter-input-topic"
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_subscription" "formatter_input_sub" {
  name  = "formatter-input-sub"
  topic = google_pubsub_topic.formatter_input.name

  push_config {
    push_endpoint = google_cloud_run_v2_service.formatter.uri
    oidc_token {
      service_account_email = google_service_account.formatter_service_account.email
    }
  }
}

# Formatter -> Orchestratore
resource "google_pubsub_topic" "formatter_output" {
  name = "formatter-output-topic"
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_subscription" "formatter_output_sub" {
  name  = "formatter-output-sub"
  topic = google_pubsub_topic.formatter_output.name
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.orchestratore.uri}/receive_analysis_results"
    oidc_token {
      service_account_email = google_service_account.orchestratore_service_account.email
    }
  }
}

# Orchestratore -> Anonymizer
resource "google_pubsub_topic" "anonymizer_input" {
  name = "anonymizer-input-topic"
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_subscription" "anonymizer_input_sub" {
  name  = "anonymizer-input-sub"
  topic = google_pubsub_topic.anonymizer_input.name

  push_config {
    push_endpoint = google_cloud_run_v2_service.anonymizer.uri
    oidc_token {
      service_account_email = google_service_account.anonymizer_service_account.email
    }
  }
}

# Anonymizer -> Orchestratore
resource "google_pubsub_topic" "anonymizer_output" {
  name = "anonymizer-output-topic"
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_subscription" "anonymizer_output_sub" {
  name  = "anonymizer-output-sub"
  topic = google_pubsub_topic.anonymizer_output.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.orchestratore.uri}/receive_anonymization_results"
    oidc_token {
      service_account_email = google_service_account.orchestratore_service_account.email
    }
  }
}

#error topic
resource "google_pubsub_topic" "error_informations" {
  name = "error-information-topic"
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_subscription" "error_informations_sub" {
  name = "error-information-sub"
  topic = google_pubsub_topic.error_informations.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.orchestratore.uri}/receive_error_notifications"
    oidc_token {
      service_account_email = google_service_account.orchestratore_service_account.email
    }
  }
}

resource "google_cloud_run_v2_service" "anonymizer" {
  name     = "anonymizer"
  location = var.region

  template {
    service_account = google_service_account.anonymizer_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
    containers {
      image = "gcr.io/${var.project}/anonymizer:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT_ID"
        value = var.project
      }
      env {
        name  = "ANONYMIZER_OUTPUT_TOPIC"
        value = google_pubsub_topic.anonymizer_output.name
      }
      env {
        name  = "ERROR_INFORMATIONS_TOPIC"
        value = google_pubsub_topic.error_informations.name
      }
      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }
    }
    timeout = "300s"
    max_instance_request_concurrency = 1000
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [google_project_service.run]
}

resource "google_cloud_run_v2_service" "formatter" {
  name     = "formatter"
  location = var.region

  template {
    service_account = google_service_account.formatter_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
    containers {
      image = "gcr.io/${var.project}/formatter:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT_ID"
        value = var.project
      }
      env {
        name  = "FORMATTER_OUTPUT_TOPIC"
        value = google_pubsub_topic.formatter_output.name
      }
      env {
        name  = "ERROR_INFORMATIONS_TOPIC"
        value = google_pubsub_topic.error_informations.name
      }
      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }
    }
    timeout = "300s"
    max_instance_request_concurrency = 1000
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [google_project_service.run]
}

# Cloud Run Frontend Service
resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  location = var.region

  template {
    service_account = google_service_account.frontend_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
    containers {
      image = "gcr.io/${var.project}/frontend:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.orchestratore.uri
      }
      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }
    }
    timeout = "300s"
    max_instance_request_concurrency = 1000
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [google_project_service.run]
}

# Cloud Run Orchestratore Service (Backend principale)
resource "google_cloud_run_v2_service" "orchestratore" {
  name     = "orchestratore"
  location = var.region

  template {
    service_account = google_service_account.orchestratore_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
    containers {
      image = "gcr.io/${var.project}/orchestratore:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.main_db.private_ip_address
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.db.name
      }
      env {
        name  = "DB_USER"
        value = google_sql_user.users.name
      }
      env {
        name  = "DB_PASSWORD"
        value = var.db_password
      }
      env {
        name  = "BUCKET_NAME"
        value = google_storage_bucket.csv_bucket.name
      }
      env {
        name  = "FORMATTER_INPUT_TOPIC"
        value = google_pubsub_topic.formatter_input.name
      }
      env {
        name  = "ANONYMIZER_INPUT_TOPIC"
        value = google_pubsub_topic.anonymizer_input.name
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT_ID"
        value = var.project
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }
    }
    timeout = "300s"
    max_instance_request_concurrency = 1000
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [google_project_service.run]
}

# Output URLs e nomi risorse
output "frontend_url" {
  description = "L'URL del frontend"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "orchestratore_url" {
  description = "L'URL del backend orchestratore"
  value       = google_cloud_run_v2_service.orchestratore.uri
}

output "db_instance_connection_name" {
  description = "Nome connessione database"
  value = google_sql_database_instance.main_db.connection_name
}

output "db_private_ip" {
  description = "IP privato del database"
  value = google_sql_database_instance.main_db.private_ip_address
}

output "db_user" {
  description = "Username del database"
  value = google_sql_user.users.name
}

output "bucket_name" {
  description = "Nome del bucket per i file CSV"
  value = google_storage_bucket.csv_bucket.name
}

output "formatter_input_topic" {
  description = "Nome del topic input per il formatter"
  value = google_pubsub_topic.formatter_input.name
}

output "formatter_output_topic" {
  description = "Nome del topic output per il formatter"
  value = google_pubsub_topic.formatter_output.name
}

output "anonymizer_input_topic" {
  description = "Nome del topic input per l'anonymizer"
  value = google_pubsub_topic.anonymizer_input.name
}

output "anonymizer_output_topic" {
  description = "Nome del topic output per l'anonymizer"
  value = google_pubsub_topic.anonymizer_output.name
}

# Dashboard di monitoraggio
resource "google_monitoring_dashboard" "cloudrun_dashboard" {
  dashboard_json = jsonencode({
    displayName = "AnonimaData Dashboard"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          xPos   = 0
          yPos   = 0
          widget = {
            title = "Cloud Run Services - Requests"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      perSeriesAligner = "ALIGN_RATE"
                      alignmentPeriod = "60s"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Requests/sec"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          xPos   = 6
          yPos   = 0
          widget = {
            title = "Cloud Run Services - Latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      perSeriesAligner = "ALIGN_PERCENTILE_95"
                      alignmentPeriod = "60s"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Latency (ms)"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          xPos   = 0
          yPos   = 4
          widget = {
            title = "Cloud Run Jobs - Executions"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_job\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\""
                    aggregation = {
                      perSeriesAligner = "ALIGN_RATE"
                      alignmentPeriod = "60s"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Executions/sec"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          width  = 6
          height = 4
          xPos   = 6
          yPos   = 4
          widget = {
            title = "Pub/Sub Messages"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"pubsub_topic\" AND metric.type=\"pubsub.googleapis.com/topic/send_message_operation_count\""
                    aggregation = {
                      perSeriesAligner = "ALIGN_RATE"
                      alignmentPeriod = "60s"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Messages/sec"
                scale = "LINEAR"
              }
            }
          }
        }
      ]
    }
  })
}