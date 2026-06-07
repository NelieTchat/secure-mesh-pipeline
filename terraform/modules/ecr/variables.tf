variable "cluster_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "repositories" {
  type        = list(string)
  description = "List of ECR repository names to create"
  default = [
    "frontend",
    "backend",
    "api-service"
  ]
}

variable "image_retention_count" {
  type        = number
  description = "Number of images to retain per repository"
  default     = 10
}

variable "github_actions_role_arn" {
  type        = string
  description = "IAM role ARN for GitHub Actions — granted push access"
}