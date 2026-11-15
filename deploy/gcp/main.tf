# SCAFFOLD ONLY. Frontend/backend are intentionally publicly invokable for synthetic-data demo.
# Inference is protected with Cloud Run Invoker IAM. No end-user auth is supplied.
locals {
  required_apis = toset(["run.googleapis.com", "artifactregistry.googleapis.com", "iam.googleapis.com"])
}

resource "google_project_service" "required" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.prefix}-images"
  format        = "DOCKER"
  description   = "Images for synthetic-record R&D demo"
  depends_on    = [google_project_service.required]
}

resource "google_service_account" "frontend" {
  account_id   = "${var.prefix}-frontend"
  display_name = "NRL Frontend Demo"
  depends_on   = [google_project_service.required]
}

resource "google_service_account" "backend" {
  account_id   = "${var.prefix}-backend"
  display_name = "NRL Backend Demo"
  depends_on   = [google_project_service.required]
}

resource "google_service_account" "inference" {
  account_id   = "${var.prefix}-inference"
  display_name = "NRL Inference Demo"
  depends_on   = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "inference" {
  project             = var.project_id
  name                = "${var.prefix}-inference"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # IAM-protected, not network-private
  deletion_protection = false # DEMO ONLY
  template {
    service_account = google_service_account.inference.email
    timeout         = "300s"
    max_instance_request_concurrency = 1
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      name       = "inference"
      image      = var.inference_image
      depends_on = ["ollama"]
      ports {
        container_port = 8100
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "OLLAMA_URL"
        value = "http://127.0.0.1:11434"
      }
      env {
        name  = "MODEL_NAME"
        value = var.model_name
      }
      env {
        name  = "OLLAMA_TIMEOUT_SECONDS"
        value = "180"
      }
    }
    containers {
      name  = "ollama"
      image = var.ollama_image
      resources {
        limits = { cpu = "2", memory = "3Gi" }
      }
      env {
        name  = "OLLAMA_HOST"
        value = "0.0.0.0:11434"
      }
      startup_probe {
        http_get {
          path = "/api/tags"
          port = 11434
        }
        initial_delay_seconds = 0
        timeout_seconds       = 5
        period_seconds        = 5
        failure_threshold     = 24
      }
    }
  }
  depends_on = [google_project_service.required]
}

# Only the backend service account is allowed to invoke the inference service.
resource "google_cloud_run_v2_service_iam_member" "backend_invokes_inference" {
  project  = var.project_id
  location = google_cloud_run_v2_service.inference.location
  name     = google_cloud_run_v2_service.inference.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_cloud_run_v2_service" "backend" {
  project             = var.project_id
  name                = "${var.prefix}-backend"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # DEMO ONLY
  template {
    service_account = google_service_account.backend.email
    timeout         = "300s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      name  = "backend"
      image = var.backend_image
      ports {
        container_port = 8000
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "INFERENCE_URL"
        value = google_cloud_run_v2_service.inference.uri
      }
      env {
        name  = "INFERENCE_AUTH_MODE"
        value = "google_id_token"
      }
      env {
        name  = "INFERENCE_AUDIENCE"
        value = google_cloud_run_v2_service.inference.uri
      }
      env {
        name  = "INFERENCE_TIMEOUT_SECONDS"
        value = "195"
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.frontend_origin
      }
    }
  }
  depends_on = [google_cloud_run_v2_service_iam_member.backend_invokes_inference]
}

resource "google_cloud_run_v2_service_iam_member" "public_backend" {
  project  = var.project_id
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers" # PUBLIC demo API; add real user authentication before any sensitive data
}

resource "google_cloud_run_v2_service" "frontend" {
  project             = var.project_id
  name                = "${var.prefix}-frontend"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # DEMO ONLY
  template {
    service_account = google_service_account.frontend.email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      name  = "frontend"
      image = var.frontend_image
      ports {
        container_port = 80 # nginx.conf in current frontend production stage listens on 80
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
    }
  }
  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "public_frontend" {
  project  = var.project_id
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers" # Synthetic-data demo only
}
