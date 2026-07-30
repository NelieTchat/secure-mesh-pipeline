###############################################################################
# API Gateway — Private Webhook Endpoint
#
# ROLE: Receives webhook POST requests from AlertManager inside the cluster
# and triggers the Lambda function.
#
# SECURITY:
#   - Private endpoint — only accessible from inside the VPC
#   - Not exposed to the public internet (GovCloud requirement)
#   - VPC endpoint restricts access to cluster traffic only
###############################################################################

resource "aws_api_gateway_rest_api" "aiops" {
  name        = "${var.lambda_function_name}-api"
  description = "Private API Gateway for AIOps alert webhook"

  # PRIVATE — only accessible from inside the VPC
  endpoint_configuration {
    types            = ["PRIVATE"]
    vpc_endpoint_ids = [aws_vpc_endpoint.api_gateway.id]
  }

  tags = {
    Name    = "${var.lambda_function_name}-api"
    Purpose = "AIOps webhook endpoint"
  }
}

# VPC Endpoint — allows traffic from inside the VPC to reach API Gateway
# without going through the public internet
resource "aws_vpc_endpoint" "api_gateway" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.execute-api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.api_gateway.id]

  private_dns_enabled = true

  tags = {
    Name    = "${var.lambda_function_name}-vpc-endpoint"
    Purpose = "Private API Gateway VPC endpoint"
  }
}

# Security group for API Gateway VPC endpoint
resource "aws_security_group" "api_gateway" {
  name        = "${var.lambda_function_name}-apigw-sg"
  description = "Security group for API Gateway VPC endpoint"
  vpc_id      = var.vpc_id

  # Allow HTTPS from inside the VPC only
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "HTTPS from VPC only"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.lambda_function_name}-apigw-sg"
  }
}

# API resource — /alert endpoint
resource "aws_api_gateway_resource" "alert" {
  rest_api_id = aws_api_gateway_rest_api.aiops.id
  parent_id   = aws_api_gateway_rest_api.aiops.root_resource_id
  path_part   = "alert"
}

# POST method — AlertManager sends POST requests
resource "aws_api_gateway_method" "alert_post" {
  rest_api_id   = aws_api_gateway_resource.alert.rest_api_id
  resource_id   = aws_api_gateway_resource.alert.id
  http_method   = "POST"
  authorization = "NONE"
}