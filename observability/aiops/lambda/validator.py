"""
validator.py — Alert Validation Layer
Steps 2, 3, 4, 14 of the AIOps pipeline.

Responsibilities:
  - Validate incoming alert structure
  - Normalize alert fields to a standard format
  - Detect and prevent duplicate alert processing
  - Validate Claude's AI response before acting on it
"""

import logging
import hashlib
from datetime import datetime, timezone
from utils import safe_default

logger = logging.getLogger()


###############################################################################
# STEP 2 — VALIDATE
###############################################################################

def validate_alert(alert):
    """
    Confirms the alert has all required fields.
    Rejects malformed payloads before any processing.
    """
    required_fields = ["labels", "annotations", "status"]
    for field in required_fields:
        if field not in alert:
            return False, f"Missing required field: {field}"

    if "alertname" not in alert.get("labels", {}):
        return False, "Missing alertname in labels"

    return True, None


###############################################################################
# STEP 3 — NORMALIZE
###############################################################################

def normalize_alert(alert):
    """
    Standardizes alert format regardless of source.
    All downstream functions use normalized fields — never raw alert.
    """
    labels      = alert.get("labels", {})
    annotations = alert.get("annotations", {})

    return {
        "alert_name":  labels.get("alertname", "Unknown"),
        "namespace":   labels.get("namespace", "default"),
        "pod":         labels.get("pod", "unknown"),
        "severity":    labels.get("severity", "warning"),
        "service":     labels.get("service", labels.get("destination_service_name", "unknown")),
        "summary":     annotations.get("summary", "No summary"),
        "description": annotations.get("description", "No description"),
        "status":      alert.get("status", "firing"),
        "raw":         alert
    }


###############################################################################
# STEP 4 — DEDUPLICATE
###############################################################################

def check_duplicate(alert, table):
    """
    Generates a fingerprint from alert_name + namespace + pod.
    Checks DynamoDB for a recent incident with the same fingerprint.
    Prevents the same alert from being processed multiple times
    within a 10-minute window.
    """
    try:
        response = table.query(
            IndexName="AlertNameIndex",
            KeyConditionExpression="alert_name = :name",
            ExpressionAttributeValues={":name": alert["alert_name"]},
            Limit=1,
            ScanIndexForward=False
        )
        items = response.get("Items", [])
        if items:
            last      = items[0]
            last_time = datetime.fromisoformat(last["timestamp"])
            now       = datetime.now(timezone.utc)
            diff_min  = (now - last_time).seconds / 60
            if diff_min < 10:
                return True, last["incident_id"]
    except Exception as e:
        logger.warning(f"Dedup check failed: {e}")

    return False, None


###############################################################################
# STEP 14 — VALIDATE AI RESPONSE
###############################################################################

def validate_ai_response(analysis):
    """
    Validates Claude's response has required fields and valid values.
    Never trust AI output blindly — always validate before acting.
    """
    required_fields = [
        "root_cause", "recommended_action", "confidence",
        "risk_level", "auto_executable"
    ]

    for field in required_fields:
        if field not in analysis:
            logger.warning(f"Missing field in AI response: {field}")
            return safe_default(f"Missing required field: {field}")

    # Validate confidence is a valid float between 0 and 1
    try:
        confidence = float(analysis["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError
        analysis["confidence"] = confidence
    except (ValueError, TypeError):
        logger.warning("Invalid confidence value — defaulting to 0.0")
        analysis["confidence"] = 0.0

    # Validate risk_level is one of the allowed values
    if analysis["risk_level"] not in ["LOW", "MEDIUM", "HIGH"]:
        logger.warning(f"Invalid risk_level: {analysis['risk_level']} — defaulting to HIGH")
        analysis["risk_level"] = "HIGH"

    # Validate auto_executable is boolean
    if not isinstance(analysis["auto_executable"], bool):
        analysis["auto_executable"] = False

    return analysis