output "frontend_url" {
  description = "CloudFront URL. Upload the built dist/ files to frontend_bucket."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "backend_demo_alb" {
  description = "HTTP-only ALB for demo; do not use for real records."
  value       = "http://${aws_lb.backend.dns_name}"
}

output "ecr_repository_urls" {
  value = { for name, repo in aws_ecr_repository.images : name => repo.repository_url }
}

output "private_inference_dns" {
  value = "http://inference.nrl.internal:8100"
}
