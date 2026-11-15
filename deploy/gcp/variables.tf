variable "project_id" {
  description = "Existing GCP project ID with billing enabled."
  type        = string
}
variable "region" {
  type    = string
  default = "asia-northeast1"
}
variable "prefix" {
  type    = string
  default = "nrl-demo"
}
variable "frontend_image" {
  description = "Prebuilt frontend production Nginx image. VITE_API_BASE_URL must be baked at build time."
  type        = string
}
variable "backend_image" {
  type = string
}
variable "inference_image" {
  type = string
}
variable "ollama_image" {
  description = "Custom image with qwen3:0.6b pre-installed; stock ollama/ollama will show model_not_found."
  type        = string
}
variable "frontend_origin" {
  description = "Exact frontend https origin, including scheme and no trailing slash, for FastAPI CORS."
  type        = string
}
variable "model_name" {
  type    = string
  default = "qwen3:0.6b"
}
