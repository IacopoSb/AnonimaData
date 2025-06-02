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

# Service Account base (senza permessi speciali)
resource "google_service_account" "app_service_account" {
  account_id   = "anonidata-app"
  display_name = "AnoniData Application Service Account"
}

# Cloud Run Servizio Anonymizer (interno, no auth)
resource "google_cloud_run_v2_service" "anonymizer" {
  name     = "anonymizer"
  location = var.region

  template {
    service_account = google_service_account.app_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
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
  
  depends_on = [google_project_service.run]
}

# Cloud Run Servizio Formatter (interno, no auth)
resource "google_cloud_run_v2_service" "formatter" {
  name     = "formatter"
  location = var.region

  template {
    service_account = google_service_account.app_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
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
  
  depends_on = [google_project_service.run]
}

# Cloud Run Frontend (privato per ora)
resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  location = var.region

  template {
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
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
    service_account = google_service_account.app_service_account.email
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
    containers {
      image = "gcr.io/${var.project}/orchestratore:latest"
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
  }
}

# IAM: Solo l'orchestratore è pubblico
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

# Permessi minimi per Storage (solo se necessario)
resource "google_project_iam_member" "app_storage_access" {
  project = var.project
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
  
  count = 1
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

output "db_private_ip" {
  value = google_sql_database_instance.main_db.private_ip_address
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