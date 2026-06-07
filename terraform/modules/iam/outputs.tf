output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "eks_node_role_arn" {
  value = aws_iam_role.eks_node.arn
}