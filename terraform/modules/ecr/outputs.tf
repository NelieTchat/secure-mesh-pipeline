output "repository_urls" {
  value = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "repository_arns" {
  value = [for v in aws_ecr_repository.services : v.arn]
}