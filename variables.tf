variable "project" {
  description = "ID del progetto GCP"
  type        = string
  default     = ""
}

variable "region" {
  description = "Regione GCP in cui distribuire le risorse"
  type        = string
default     = "europe-central2"
}

variable "credentials_file" {
  description = "Percorso al file JSON delle credenziali di Google Cloud"
  type        = string
}
