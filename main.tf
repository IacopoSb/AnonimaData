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

  settings {
    tier = "db-f1-micro"
    ip_configuration {
      ipv4_enabled    = false
      private_network = var.vpc_network
    }
  }
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

# Cloud Run Orchestratore (Backend principale)
resource "google_cloud_run_service" "orchestratore" {
  name     = "orchestratore"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project}/orchestratore:latest"
        env {
          name  = "DB_CONNECTION_STRING"
          value = "postgresql://${google_sql_user.users.name}:${var.db_password}@/appdb?host=/cloudsql/${google_sql_database_instance.main_db.connection_name}"
        }
        env {
          name  = "FORMATTER_URL"
          value = google_cloud_run_service.formatter.status[0].url
        }
        env {
          name  = "ANONYMIZER_URL"
          value = google_cloud_run_service.anonymizer.status[0].url
        }
        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1"
          }
        }
      }
      service_account_name = google_service_account.orchestratore_invoker.email
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Cloud Run Servizio Anonymizer
resource "google_cloud_run_service" "anonymizer" {
  name     = "anonymizer"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project}/anonymizer:latest"
        resources {
          limits = {
            memory = "256Mi"
            cpu    = "0.5"
          }
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Cloud Run Servizio Formatter
resource "google_cloud_run_service" "formatter" {
  name     = "formatter"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project}/formatter:latest"
        resources {
          limits = {
            memory = "256Mi"
            cpu    = "0.5"
          }
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# # Frontend
# resource "google_cloud_run_service" "frontend_service" {
#   name     = "frontend"
#   location = var.region
# 
#   template {
#     spec {
#       containers {
#         image = "gcr.io/${var.project}/frontend:latest"
#         resources {
#           limits = {
#             memory = "256Mi"
#             cpu    = "0.5"
#           }
#         }
#       }
#     }
#   }
#   traffic {
#     percent         = 100
#     latest_revision = true
#   }
# }

# IAM: Frontend e orchestratore sono pubblici
data "google_iam_policy" "public_invoker" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

# resource "google_cloud_run_service_iam_policy" "frontend_policy" {
#   location    = google_cloud_run_service.frontend_service.location
#   project     = var.project
#   service     = google_cloud_run_service.frontend_service.name
#   policy_data = data.google_iam_policy.public_invoker.policy_data
# }

resource "google_cloud_run_service_iam_policy" "orchestratore_policy" {
  location    = google_cloud_run_service.orchestratore.location
  project     = var.project
  service     = google_cloud_run_service.orchestratore.name
  policy_data = data.google_iam_policy.public_invoker.policy_data
}

# IAM: anonymizer e formatter sono invocabili solo dall'orchestratore (tramite service account)
resource "google_service_account" "orchestratore_invoker" {
  account_id   = "orchestratore-invoker"
  display_name = "Orchestratore Cloud Run Invoker"
}

resource "google_cloud_run_service_iam_member" "anonymizer_invoker" {
  location    = google_cloud_run_service.anonymizer.location
  project     = var.project
  service     = google_cloud_run_service.anonymizer.name
  role        = "roles/run.invoker"
  member      = "serviceAccount:${google_service_account.orchestratore_invoker.email}"
}

resource "google_cloud_run_service_iam_member" "formatter_invoker" {
  location    = google_cloud_run_service.formatter.location
  project     = var.project
  service     = google_cloud_run_service.formatter.name
  role        = "roles/run.invoker"
  member      = "serviceAccount:${google_service_account.orchestratore_invoker.email}"
}

# # Output URLs
# output "frontend_service_url" {
#   description = "L'URL del servizio Cloud Run per il frontend"
#   value       = google_cloud_run_service.frontend_service.status[0].url
# }

output "orchestratore_url" {
  description = "L'URL del backend orchestratore"
  value       = google_cloud_run_service.orchestratore.status[0].url
}

output "anonymizer_url" {
  description = "L'URL del anonymizer (interno)"
  value       = google_cloud_run_service.anonymizer.status[0].url
}

output "formatter_url" {
  description = "L'URL del formatter (interno)"
  value       = google_cloud_run_service.formatter.status[0].url
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


# Dashboard 
resource "google_monitoring_dashboard" "cloudrun_dashboard" {
  dashboard_json = jsonencode({
    displayName = "AnonimaData Dashboard"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Cloud Run Requests"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" metric.type=\"run.googleapis.com/request_count\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_RATE"
                    alignmentPeriod = "60s"
                  }
                }
              }
              plotType = "LINE"
            }]
            timeshiftDuration = "0s"
            yAxis = {
              label = "Requests/sec"
              scale = "LINEAR"
            }
          }
        },
        {
          title = "Cloud Run Errors"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" metric.type=\"run.googleapis.com/error_count\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_RATE"
                    alignmentPeriod = "60s"
                  }
                }
              }
              plotType = "LINE"
            }]
            timeshiftDuration = "0s"
            yAxis = {
              label = "Errors/sec"
              scale = "LINEAR"
            }
          }
        },
        {
          title = "Cloud Run Latency"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" metric.type=\"run.googleapis.com/request_latencies\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_PERCENTILE_95"
                    alignmentPeriod = "60s"
                  }
                }
              }
              plotType = "LINE"
            }]
            timeshiftDuration = "0s"
            yAxis = {
              label = "Latency (ms)"
              scale = "LINEAR"
            }
          }
        }
      ]
    }
  })
}