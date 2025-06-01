variable "project" {
  description = "ID del progetto GCP"
  type        = string
}

variable "region" {
  description = "Regione GCP in cui distribuire le risorse"
  type        = string
}

variable "db_password" {
  description = "Password for the Cloud SQL user"
  type        = string
  sensitive   = true
}

variable "vpc_network" {
  description = "Self link or name of the VPC network for Cloud SQL private IP"
  type        = string
}