terraform {
  required_version = ">= 0.14"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0" 
    }
  }
}

# Configurazione del provider GCP
provider "google" {
  project     = var.project
  region      = var.region
  credentials = file(var.credentials_file) 
}

# Creazione di un bucket per salvare i file CSV
resource "google_storage_bucket" "csv_bucket" {
  name                          = "${var.project}-csv-bucket"
  location                      = var.region
  force_destroy                 = true  # Permette la cancellazione del bucket anche se contiene oggetti
  uniform_bucket_level_access   = true
}

# Creazione di un servizio Cloud Run per il backend API
resource "google_cloud_run_service" "backend_service" {
  name     = "backend"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project}/backend:latest"  
        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1"
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

# Configurazione della policy IAM per permettere al servizio di essere invocato (ad es. da utenti esterni)
resource "google_iam_policy" "run_invoker" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

resource "google_cloud_run_service_iam_policy" "backend_service_policy" {
  location    = google_cloud_run_service.backend_service.location
  project     = var.project
  service     = google_cloud_run_service.backend_service.name

  policy_data = google_iam_policy.run_invoker.policy_data
}

# Output per visualizzare l'URL del servizio Cloud Run
output "backend_service_url" {
  description = "L'URL del servizio Cloud Run per il backend API"
  value       = google_cloud_run_service.backend_service.status[0].url
}

# Analogo per il frontend

resource "google_cloud_run_service" "frontend_service" {
  name     = "frontend"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project}/frontend:latest"
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

resource "google_cloud_run_service_iam_policy" "frontend_policy" {
  location    = google_cloud_run_service.frontend_service.location
  project     = var.project
  service     = google_cloud_run_service.frontend_service.name

  policy_data = google_iam_policy.run_invoker.policy_data
}

output "frontend_service_url" {
  description = "L'URL del servizio Cloud Run per il frontend"
  value       = google_cloud_run_service.frontend_service.status[0].url
}
