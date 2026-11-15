variable "aws_region" {
  description = "AWS deployment region."
  type        = string
  default     = "ap-northeast-1"
}

variable "prefix" {
  description = "Unique lowercase resource prefix; keep under ~20 characters."
  type        = string
  default     = "nrl-demo"
}

variable "backend_image" {
  description = "Pre-pushed FastAPI backend image URI (immutable digest recommended)."
  type        = string
}

variable "inference_image" {
  description = "Pre-pushed FastAPI inference image URI."
  type        = string
}

variable "ollama_image" {
  description = "Ollama image WITH qwen3:0.6b already available inside /root/.ollama (NOT stock Ollama image)."
  type        = string
}

variable "model_name" {
  type    = string
  default = "qwen3:0.6b"
}

variable "desired_count" {
  description = "Desired number of tasks per service (1 for isolated mock demo)."
  type        = number
  default     = 1
}
