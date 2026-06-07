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