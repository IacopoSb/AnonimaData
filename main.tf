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

# VPC Peering per Cloud SQL Private IP
resource "google_compute_global_address" "private_ip_address" {
  name          = "sql-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = var.vpc_network
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = var.vpc_network
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
  depends_on              = [google_compute_global_address.private_ip_address]
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

  depends_on = [google_service_networking_connection.private_vpc_connection]
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

# Service Account per l'orchestratore (deve essere creato prima dei servizi)
resource "google_service_account" "orchestratore_invoker" {
  account_id   = "orchestratore-invoker"
  display_name = "Orchestratore Cloud Run Invoker"
}

# Permessi per il service account di accedere a Cloud SQL e Storage
resource "google_project_iam_member" "orchestratore_sql_client" {
  project = var.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.orchestratore_invoker.email}"
}

resource "google_project_iam_member" "orchestratore_storage_admin" {
  project = var.project
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.orchestratore_invoker.email}"
}

# Cloud Run Servizio Anonymizer
resource "google_cloud_run_v2_service" "anonymizer" {
  name     = "anonymizer"
  location = var.region

  template {
    service_account = google_service_account.orchestratore_invoker.email
    containers {
      image = "gcr.io/${var.project}/anonymizer:latest"
      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }
    }
  }
}

# Cloud Run Servizio Formatter
resource "google_cloud_run_v2_service" "formatter" {
  name     = "formatter"
  location = var.region

  template {
    service_account = google_service_account.orchestratore_invoker.email
    containers {
      image = "gcr.io/${var.project}/formatter:latest"
      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }
    }
  }
}

# Cloud Run Frontend (commentato ma pronto per il futuro)
resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  location = var.region

  template {
    containers {
      image = "gcr.io/${var.project}/frontend:latest"
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
  }
}

# Cloud Run Orchestratore (Backend principale)
resource "google_cloud_run_v2_service" "orchestratore" {
  name     = "orchestratore"
  location = var.region

  template {
    service_account = google_service_account.orchestratore_invoker.email
    containers {
      image = "gcr.io/${var.project}/orchestratore:latest"
      env {
        name  = "DB_CONNECTION_STRING"
        value = "postgresql://${google_sql_user.users.name}:${var.db_password}@/appdb?host=/cloudsql/${google_sql_database_instance.main_db.connection_name}"
      }
      env {
        name  = "FORMATTER_URL"
        value = google_cloud_run_v2_service.formatter.uri
      }
      env {
        name  = "ANONYMIZER_URL"
        value = google_cloud_run_v2_service.anonymizer.uri
      }
      env {
        name  = "BUCKET_NAME"
        value = google_storage_bucket.csv_bucket.name
      }
      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }
    }
    annotations = {
      "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.main_db.connection_name
    }
  }
}

# IAM: Orchestratore è pubblico
resource "google_cloud_run_v2_service_iam_member" "orchestratore_public" {
  location = google_cloud_run_v2_service.orchestratore.location
  name     = google_cloud_run_v2_service.orchestratore.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# IAM: Frontend pubblico (commentato, decommentare quando necessario)
# resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
#   location = google_cloud_run_v2_service.frontend.location
#   name     = google_cloud_run_v2_service.frontend.name
#   role     = "roles/run.invoker"
#   member   = "allUsers"
# }

# IAM: Anonymizer e Formatter sono invocabili solo dall'orchestratore
resource "google_cloud_run_v2_service_iam_member" "anonymizer_invoker" {
  location = google_cloud_run_v2_service.anonymizer.location
  name     = google_cloud_run_v2_service.anonymizer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.orchestratore_invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "formatter_invoker" {
  location = google_cloud_run_v2_service.formatter.location
  name     = google_cloud_run_v2_service.formatter.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.orchestratore_invoker.email}"
}

# Output URLs
output "frontend_url" {
  description = "L'URL del frontend (attualmente privato)"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "orchestratore_url" {
  description = "L'URL del backend orchestratore"
  value       = google_cloud_run_v2_service.orchestratore.uri
}

output "anonymizer_url" {
  description = "L'URL del anonymizer (interno)"
  value       = google_cloud_run_v2_service.anonymizer.uri
}

output "formatter_url" {
  description = "L'URL del formatter (interno)"
  value       = google_cloud_run_v2_service.formatter.uri
}

output "db_instance_connection_name" {
  value = google_sql_database_instance.main_db.connection_name
}

output "db_user" {
  value = google_sql_user.users.name
}

output "bucket_name" {
  value = google_storage_bucket.csv_bucket.name
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
            title = "Cloud Run Requests"
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
            title = "Cloud Run Latency"
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
        }
      ]
    }
  })
}