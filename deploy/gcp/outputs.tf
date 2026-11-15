output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}
output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}
output "inference_url_iam_protected" {
  value = google_cloud_run_v2_service.inference.uri
}
output "artifact_registry_repository" {
  value = google_artifact_registry_repository.images.name
}
