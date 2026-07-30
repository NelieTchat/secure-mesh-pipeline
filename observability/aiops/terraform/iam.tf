###############################################################################
# IAM for AIOps Lambda
# Lambda needs permissions to:
#   - Call Amazon Bedrock (Claude)
#   - Read from EKS API (describe cluster, get pod status)
#   - Read CloudWatch logs (recent pod logs for context)
#   - Read/Write DynamoDB (incident history)
#   - Read Secrets Manager (Slack webhook URL)
#   - Write CloudWatch logs (Lambda execution logs)
# All via IAM role — no hardcoded credentials (GovCloud requirement)
###############################################################################

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "aiops_lambda" {
  name = "${var.lambda_function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name    = "${var.lambda_function_name}-role"
    Purpose = "AIOps Lambda execution role"
  }
}

resource "aws_iam_role_policy" "aiops_lambda_policy" {
  name = "${var.lambda_function_name}-policy"
  role = aws_iam_role.aiops_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Call Amazon Bedrock — Claude model only
        Sid    = "BedrockInvokeModel"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      },
      {
        # Read EKS cluster details for context enrichment
        Sid    = "EKSDescribe"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListNodegroups"
        ]
        Resource = "arn:aws:eks:${var.aws_region}:${data.aws_caller_identity.current.account_id}:cluster/${var.cluster_name}"
      },
      {
        # Read CloudWatch logs for recent pod logs
        Sid    = "CloudWatchLogsRead"
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        # Write Lambda execution logs to CloudWatch
        Sid    = "CloudWatchLogsWrite"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_function_name}:*"
      },
      {
        # DynamoDB — read and write incident history
        Sid    = "DynamoDBIncidents"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_name}"
      },
      {
        # Read Slack webhook URL from Secrets Manager
        Sid    = "SecretsManagerRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.slack_webhook_secret_arn
      },
      {
        # VPC networking — required for VPC-bound Lambda
        Sid    = "VPCNetworking"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}