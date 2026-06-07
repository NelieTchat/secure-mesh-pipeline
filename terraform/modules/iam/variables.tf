variable "cluster_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "github_org" {
  type        = string
  description = "Your GitHub username or organization"
}

variable "github_repo" {
  type        = string
  description = "Your GitHub repository name"
}