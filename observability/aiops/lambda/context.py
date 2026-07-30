"""
context.py — Context Gathering Layer
Steps 6, 7, 8, 9, 10, 11 of the AIOps pipeline.

Responsibilities:
  - Gather current Kubernetes pod status
  - Pull recent pod logs from CloudWatch
  - Retrieve incident history from DynamoDB
  - Load approved runbook from S3
  - Determine business context (time, environment)
  - Correlate related alerts
"""

import logging
import boto3
import os
from datetime import datetime, timezone

logger = logging.getLogger()

EKS_CLUSTER_NAME = os.environ["EKS_CLUSTER_NAME"]
AWS_REGION_NAME  = os.environ["AWS_REGION_NAME"]
ENVIRONMENT      = os.environ["ENVIRONMENT"]
RUNBOOK_BUCKET   = os.environ.get("RUNBOOK_BUCKET", "")
OFF_HOURS_START  = 22
OFF_HOURS_END    = 6

logs_client = boto3.client("logs", region_name=AWS_REGION_NAME)
s3          = boto3.client("s3",   region_name=AWS_REGION_NAME)


###############################################################################
# STEP 6 — GATHER KUBERNETES CONTEXT
###############################################################################

def gather_k8s_context(alert):
    """
    Pulls current pod and deployment status from EKS.
    Gives Claude real-time cluster state — not just the alert metric.
    """
    context = {
        "cluster":   EKS_CLUSTER_NAME,
        "namespace": alert["namespace"],
        "pod":       alert["pod"],
        "status":    "unknown"
    }

    try:
        # Production: use kubernetes Python client with IRSA token
        context["status"] = "context_retrieval_requires_k8s_client"
        context["note"]   = "Production: use boto3 EKS token + kubernetes client"
    except Exception as e:
        logger.warning(f"K8s context failed: {e}")

    return context


###############################################################################
# STEP 7 — GATHER RECENT LOGS
###############################################################################

def gather_recent_logs(alert):
    """
    Pulls the last 20 log lines for the affected pod from CloudWatch.
    Gives Claude real application output — not just metrics.
    """
    pod       = alert["pod"]
    log_group = f"/aws/containerinsights/{EKS_CLUSTER_NAME}/application"

    try:
        response = logs_client.filter_log_events(
            logGroupName=log_group,
            filterPattern=pod,
            limit=20
        )
        return [e["message"] for e in response.get("events", [])]
    except Exception as e:
        logger.warning(f"Log retrieval failed: {e}")
        return []


###############################################################################
# STEP 8 — RETRIEVE INCIDENT HISTORY
###############################################################################

def get_incident_history(alert_name, table):
    """
    Queries DynamoDB for past incidents with this alert name.
    Tells Claude if this is a recurring problem or first occurrence.
    Recurring alerts get different treatment — root cause is likely deeper.
    """
    try:
        response = table.query(
            IndexName="AlertNameIndex",
            KeyConditionExpression="alert_name = :name",
            ExpressionAttributeValues={":name": alert_name},
            Limit=10,
            ScanIndexForward=False
        )
        items = response.get("Items", [])
        return {
            "count":            len(items),
            "is_recurring":     len(items) > 3,
            "last_occurred":    items[0]["timestamp"] if items else None,
            "recent_incidents": items
        }
    except Exception as e:
        logger.warning(f"History retrieval failed: {e}")
        return {
            "count":            0,
            "is_recurring":     False,
            "last_occurred":    None,
            "recent_incidents": []
        }


###############################################################################
# STEP 9 — LOAD RUNBOOK
###############################################################################

def load_runbook(alert_name):
    """
    Loads the approved remediation runbook from S3.
    Runbooks are company-approved — Claude uses them as guardrails.
    If no runbook exists, Claude falls back to general SRE knowledge.
    """
    if not RUNBOOK_BUCKET:
        return {"found": False, "content": None}

    key = f"runbooks/{alert_name.lower()}.md"

    try:
        response = s3.get_object(Bucket=RUNBOOK_BUCKET, Key=key)
        content  = response["Body"].read().decode("utf-8")
        return {"found": True, "content": content, "key": key}
    except Exception as e:
        logger.info(f"No runbook found for {alert_name}: {e}")
        return {"found": False, "content": None}


###############################################################################
# STEP 10 — BUSINESS CONTEXT
###############################################################################

def get_business_context():
    """
    Determines current time, environment, and off-hours status.
    Time context directly affects the graduated automation decision.
    """
    now          = datetime.now(timezone.utc)
    current_hour = now.hour
    is_off_hours = (current_hour >= OFF_HOURS_START or current_hour < OFF_HOURS_END)
    is_weekend   = now.weekday() >= 5

    return {
        "current_time":  now.isoformat(),
        "current_hour":  current_hour,
        "is_off_hours":  is_off_hours,
        "is_weekend":    is_weekend,
        "environment":   ENVIRONMENT,
        "is_production": ENVIRONMENT == "prod"
    }


###############################################################################
# STEP 11 — CORRELATE ALERTS
###############################################################################

def correlate_alerts(alert, history):
    """
    Groups related alerts into one incident.
    Prevents alert storms from generating duplicate Slack messages.
    Example: CPU + Memory + Restart alerts on the same pod
    are one incident — not three separate pages.
    """
    alert_name = alert["alert_name"]

    related_patterns = {
        "CrashLoopDetected": ["OOMKillDetected", "MemoryPressure"],
        "MemoryPressure":    ["OOMKillDetected", "CrashLoopDetected"],
        "CriticalCPU":       ["HighErrorRate"],
        "HighErrorRate":     ["CriticalCPU", "CrashLoopDetected"]
    }

    related      = related_patterns.get(alert_name, [])
    is_storm     = history["count"] > 5 and history["is_recurring"]

    return {
        "related_alerts": related,
        "is_alert_storm": is_storm,
        "pod":            alert["pod"],
        "namespace":      alert["namespace"],
        "summary":        f"{alert_name} on {alert['pod']} in {alert['namespace']}"
    }