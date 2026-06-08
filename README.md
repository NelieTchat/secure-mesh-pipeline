# secure-mesh-pipeline

A production-grade DevSecOps pipeline demonstrating end-to-end container
security, GitOps deployment, and zero-trust service mesh on AWS EKS.

## Architecture

Developer Commit
│
▼
GitHub Actions (CI Trigger)
• Keyless AWS authentication via OIDC
• Submits workflow to Argo
│
▼
Argo Workflows (Pipeline Orchestration)
• Build container image
• Scan with Trivy for CVEs
• Python CVE parser enforces threshold
• Push approved images to ECR
│
▼
ArgoCD (GitOps Deployment)
• Watches Git for changes
• Reconciles cluster to desired state
• Self-healing, automated sync
│
▼
EKS Cluster + Istio Service Mesh
• mTLS between all services
• AuthorizationPolicy enforcement
• Full observability

## What This Project Demonstrates

| Skill | Implementation |
|---|---|
| Terraform | Modular IaC — VPC, IAM, ECR, EKS |
| AWS | EKS, ECR, IAM, KMS, VPC, CloudWatch |
| GitHub Actions | OIDC keyless auth, CI trigger |
| Argo Workflows | Kubernetes-native pipeline orchestration |
| Trivy | Container vulnerability scanning |
| Python | CVE parsing and pipeline gate enforcement |
| ArgoCD | GitOps, automated sync, self-healing |
| Istio | mTLS, service identity, AuthorizationPolicy |
| RBAC | Least privilege at every layer |
| Security | Zero static credentials, defense in depth |

## Security Posture

- **No static credentials** — GitHub Actions uses OIDC short-lived tokens
- **Least privilege** — every identity has only the permissions it needs
- **Defense in depth** — Trivy in CI, ECR scan on push, Istio mTLS in cluster
- **Immutable images** — ECR tags cannot be overwritten
- **Encrypted at rest** — KMS for Kubernetes secrets, EBS volumes
- **Full auditability** — CloudWatch logs, VPC flow logs, Git as source of truth

## Project Structure

secure-mesh-pipeline/
├── .github/workflows/     # GitHub Actions CI trigger
├── k8s/
│   ├── apps/              # Application manifests (frontend, backend, api-service)
│   ├── argocd/            # ArgoCD install and Application objects
│   ├── argo-workflows/    # Pipeline WorkflowTemplate and RBAC
│   └── istio/             # Istio install and mTLS policies
└── terraform/
└── modules/
├── vpc/           # Networking foundation
├── iam/           # GitHub OIDC, node role, ArgoCD IRSA
├── ecr/           # Container registries
└── eks/           # Kubernetes cluster

## Prerequisites

- Terraform >= 1.6.0
- AWS CLI configured
- kubectl
- GitHub repository with Actions enabled

## Getting Started

### 1. Provision Infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

### 2. Update kubeconfig

```bash
aws eks update-kubeconfig --region us-east-1 --name secure-mesh-pipeline-dev
```

### 3. Install ArgoCD

```bash
kubectl apply -n argocd -f k8s/argocd/install/
```

### 4. Install Istio

```bash
istioctl apply -f k8s/istio/install/istio-operator.yaml
kubectl apply -f k8s/istio/policies/
```

### 5. Apply Argo Workflows

```bash
kubectl apply -f k8s/argo-workflows/rbac/
kubectl apply -f k8s/argo-workflows/templates/
```

### 6. Configure GitHub Secrets

Add these secrets to your GitHub repository settings:

| Secret | Value |
|---|---|
| AWS_ROLE_ARN | Output from terraform apply |
| EKS_CLUSTER_NAME | Output from terraform apply |
| ECR_REGISTRY | Output from terraform apply |

### 7. Push to main

Every commit to main triggers the full pipeline automatically.

## Pipeline Flow

1. Developer pushes code
2. GitHub Actions authenticates to AWS via OIDC
3. Argo Workflows builds and scans the image
4. Python enforces CVE threshold — blocks critical vulnerabilities
5. Approved image pushed to ECR
6. ArgoCD detects Git change and deploys to EKS
7. Istio enforces mTLS between all services