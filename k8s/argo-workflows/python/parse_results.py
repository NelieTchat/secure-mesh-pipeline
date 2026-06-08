#!/usr/bin/env python3
import json
import sys

# Configuration — change these without touching logic
TRIVY_RESULTS = "/tmp/trivy-results.json"
CRITICAL_THRESHOLD = 0

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

# Gate decision
if counts["CRITICAL"] > CRITICAL_THRESHOLD:
    print(f"PIPELINE BLOCKED — {counts['CRITICAL']} critical CVEs found")
    sys.exit(1)

print("PIPELINE PASSED — no critical CVEs")
sys.exit(0)