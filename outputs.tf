output "backend_service_url" {
  description = "L'URL del servizio Cloud Run per il backend API"
  value       = google_cloud_run_service.backend_service.status[0].url
}

output "frontend_service_url" {
  description = "L'URL del servizio Cloud Run per il frontend"
  value       = google_cloud_run_service.frontend_service.status[0].url
}
