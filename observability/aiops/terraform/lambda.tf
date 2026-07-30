###############################################################################
# Lambda — AIOps Alert Handler (Orchestrator)
#
# ROLE: Lambda is the orchestrator of the entire AIOps pipeline.
# It receives Prometheus alerts and coordinates the full response lifecycle:
#
#   1. RECEIVE   — API Gateway triggers Lambda with the AlertManager payload
#   2. ENRICH    — Lambda pulls additional context:
#                    - Pod status from EKS API
#                    - Recent logs from CloudWatch
#                    - Alert history from DynamoDB
#                    - Current time (business hours vs off-hours)
#   3. ANALYZE   — Lambda builds a structured prompt and calls Claude
#                  via Amazon Bedrock. Claude returns JSON with:
#                    - root_cause
#                    - recommended_action
#                    - confidence (0.0 to 1.0)
#                    - risk_level (LOW / MEDIUM / HIGH)
#                    - auto_executable (true / false)
#   4. DECIDE    — Lambda applies graduated automation logic:
#                    HIGH confidence + LOW risk + off-hours → auto-execute
#                    HIGH confidence + LOW risk + business hours → recommend
#                    MEDIUM risk (any time) → recommend only
#                    HIGH risk (any time) → never auto-execute
#   5. ACT       — If auto-executing: calls EKS API to restart pod,
#                  scale replicas, or delete stuck pod
#   6. NOTIFY    — Always sends Slack notification with analysis and action
#   7. LOG       — Writes full incident record to DynamoDB for audit trail
#
# SECURITY:
#   - Runs inside VPC — no public internet exposure (GovCloud requirement)
#   - Authenticates via IAM role — no hardcoded credentials anywhere
#   - Environment variables encrypted at rest with KMS
#   - All Bedrock invocations logged to CloudTrail automatically
###############################################################################

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "aiops_handler" {
  function_name = var.lambda_function_name
  description   = "AIOps alert handler — analyzes Prometheus alerts via Claude and executes remediation"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  runtime = "python3.11"
  handler = "handler.lambda_handler"
  timeout = 60
  memory_size = 256

  role = aws_iam_role.aiops_lambda.arn

  # VPC configuration — Lambda runs inside the private network
  # Required for GovCloud compliance — no public internet exposure
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      BEDROCK_MODEL_ID        = var.bedrock_model_id
      DYNAMODB_TABLE_NAME     = var.dynamodb_table_name
      SLACK_WEBHOOK_SECRET_ARN = var.slack_webhook_secret_arn
      EKS_CLUSTER_NAME        = var.cluster_name
      AWS_REGION_NAME         = var.aws_region
      ENVIRONMENT             = var.environment
    }
  }

  # Encrypt environment variables at rest with KMS
  kms_key_arn = aws_kms_key.lambda.arn

  tags = {
    Name    = var.lambda_function_name
    Purpose = "AIOps alert handler"
  }
}

# KMS key for Lambda environment variable encryption
resource "aws_kms_key" "lambda" {
  description             = "KMS key for AIOps Lambda environment variables"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.lambda_function_name}-kms"
  }
}

resource "aws_kms_alias" "lambda" {
  name          = "alias/${var.lambda_function_name}"
  target_key_id = aws_kms_key.lambda.key_id
}

# Security group for Lambda — controls what Lambda can reach inside the VPC
resource "aws_security_group" "lambda" {
  name        = "${var.lambda_function_name}-sg"
  description = "Security group for AIOps Lambda function"
  vpc_id      = var.vpc_id

  # Allow all outbound traffic — Lambda needs to reach:
  # Bedrock API, EKS API, DynamoDB, CloudWatch, Secrets Manager
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound for AWS API calls"
  }

  tags = {
    Name = "${var.lambda_function_name}-sg"
  }
}

# CloudWatch log group for Lambda execution logs
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 30

  tags = {
    Name = "${var.lambda_function_name}-logs"
  }
}