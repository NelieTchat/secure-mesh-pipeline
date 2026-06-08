locals {
  cluster_name = "${var.cluster_name}-${var.environment}"
}

module "vpc" {
  source = "./modules/vpc"

  cluster_name         = local.cluster_name
  environment          = var.environment
  vpc_cidr             = "10.0.0.0/16"
  availability_zones   = ["us-east-1a", "us-east-1b"]
  private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]
}

module "iam" {
  source = "./modules/iam"

  cluster_name = local.cluster_name
  environment  = var.environment
  aws_region   = var.aws_region
  github_org   = "NelieTchat"
  github_repo  = "secure-mesh-pipeline"
}

module "ecr" {
  source = "./modules/ecr"

  cluster_name            = local.cluster_name
  environment             = var.environment
  repositories            = ["frontend", "backend", "api-service"]
  image_retention_count   = 10
  github_actions_role_arn = module.iam.github_actions_role_arn
}

module "eks" {
  source = "./modules/eks"

  cluster_name    = local.cluster_name
  cluster_version = "1.29"
  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnet_ids

  node_group_instance_types = ["t3.medium"]
  node_group_desired_size   = 2
  node_group_min_size       = 1
  node_group_max_size       = 4

  node_role_arn = module.iam.eks_node_role_arn

  depends_on = [module.vpc, module.iam]
}

# S3 bucket for Trivy scan reports — permanent audit trail
resource "aws_s3_bucket" "trivy_reports" {
  bucket = "${local.cluster_name}-trivy-reports"

  tags = {
    Name    = "${local.cluster_name}-trivy-reports"
    Purpose = "CVE scan report storage"
  }
}

resource "aws_s3_bucket_versioning" "trivy_reports" {
  bucket = aws_s3_bucket.trivy_reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "trivy_reports" {
  bucket = aws_s3_bucket.trivy_reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "trivy_reports" {
  bucket = aws_s3_bucket.trivy_reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}