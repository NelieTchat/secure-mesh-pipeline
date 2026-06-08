#!/usr/bin/env python3
import json
import sys
import boto3
from datetime import datetime

# Configuration — change these without touching logic
TRIVY_RESULTS = "/tmp/trivy-results.json"
CRITICAL_THRESHOLD = 0
S3_BUCKET = "secure-mesh-pipeline-dev-trivy-reports"
SERVICE_NAME = "backend"

# Load Trivy scan results
with open(TRIVY_RESULTS) as f:
    data = json.load(f)

# Count vulnerabilities by severity
counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

for result in data.get("Results", []):
    for vuln in result.get("Vulnerabilities", []):
        severity = vuln.get("Severity", "UNKNOWN")
        if severity in counts:
            counts[severity] += 1

# Print report
print("========== CVE SCAN REPORT ==========")
for severity, count in counts.items():
    print(f"  {severity:<10}: {count}")
print("=====================================")

# Upload report to S3 for audit trail
try:
    s3 = boto3.client("s3")
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    s3_key = f"{SERVICE_NAME}/{timestamp}/trivy-results.json"
    s3.upload_file(TRIVY_RESULTS, S3_BUCKET, s3_key)
    print(f"Report uploaded to s3://{S3_BUCKET}/{s3_key}")
except Exception as e:
    print(f"Warning: Could not upload to S3: {e}")

# Gate decision
if counts["CRITICAL"] > CRITICAL_THRESHOLD:
    print(f"PIPELINE BLOCKED — {counts['CRITICAL']} critical CVEs found")
    sys.exit(1)

print("PIPELINE PASSED — no critical CVEs above threshold")
sys.exit(0)