variable "aws_region" {
  description = "AWS region to deploy AIOps resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "secure-mesh-pipeline-dev"
}

variable "lambda_function_name" {
  description = "Name of the AIOps Lambda function"
  type        = string
  default     = "aiops-alert-handler"
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock model ID for Claude"
  type        = string
  default     = "anthropic.claude-3-sonnet-20240229-v1:0"
}

variable "slack_webhook_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Slack webhook URL"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where Lambda will run"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Lambda VPC configuration"
  type        = list(string)
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name for incident history"
  type        = string
  default     = "aiops-incidents"
}