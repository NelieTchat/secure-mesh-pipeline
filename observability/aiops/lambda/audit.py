"""
audit.py — Audit Trail Layer
Steps 5, 19 of the AIOps pipeline.

Responsibilities:
  - Create initial incident record in DynamoDB
  - Write complete audit trail after every action
  - Required for FedRAMP compliance — every action must be traceable

GovCloud compliance:
  - Every automated action logged with timestamp and actor
  - 90-day retention via TTL
  - Point-in-time recovery enabled on DynamoDB table
"""

import logging
import boto3
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger()

AWS_REGION_NAME     = os.environ["AWS_REGION_NAME"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
ENVIRONMENT         = os.environ["ENVIRONMENT"]

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION_NAME)
table    = dynamodb.Table(DYNAMODB_TABLE_NAME)


###############################################################################
# STEP 5 — CREATE INCIDENT RECORD
###############################################################################

def create_incident_record(alert):
    """
    Creates the initial incident record in DynamoDB.
    Status starts as 'open' — updated in step 19.
    """
    incident_id = str(uuid.uuid4())

    try:
        table.put_item(Item={
            "incident_id": incident_id,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "alert_name":  alert["alert_name"],
            "namespace":   alert["namespace"],
            "pod":         alert["pod"],
            "severity":    alert["severity"],
            "status":      "open",
            "environment": ENVIRONMENT,
            "expires_at":  str(
                int(datetime.now(timezone.utc).timestamp()) + 90 * 24 * 60 * 60
            )
        })
        logger.info(f"Incident record created: {incident_id}")
    except Exception as e:
        logger.error(f"Failed to create incident record: {e}")

    return incident_id


###############################################################################
# STEP 19 — WRITE AUDIT TRAIL
###############################################################################

def write_audit_trail(incident_id, alert, analysis, decision, action_result, verification):
    """
    Writes the complete incident record to DynamoDB.
    Every field is logged — required for FedRAMP audit trail.
    Every automated action must be traceable to a timestamp and actor.
    """
    try:
        table.update_item(
            Key={
                "incident_id": incident_id,
                "timestamp":   datetime.now(timezone.utc).isoformat()
            },
            UpdateExpression="""
                SET #status            = :status,
                    root_cause         = :root_cause,
                    recommended_action = :recommended_action,
                    confidence         = :confidence,
                    risk_level         = :risk_level,
                    decision           = :decision,
                    decision_reason    = :decision_reason,
                    action_status      = :action_status,
                    kubectl_command    = :kubectl_command,
                    verified           = :verified,
                    claude_reasoning   = :reasoning,
                    escalate           = :escalate,
                    completed_at       = :completed_at
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status":             "closed",
                ":root_cause":         analysis.get("root_cause", "Unknown"),
                ":recommended_action": analysis.get("recommended_action", "Unknown"),
                ":confidence":         str(analysis.get("confidence", 0.0)),
                ":risk_level":         analysis.get("risk_level", "Unknown"),
                ":decision":           decision.get("action", "Unknown"),
                ":decision_reason":    decision.get("reason", "Unknown"),
                ":action_status":      action_result.get("status", "Unknown"),
                ":kubectl_command":    action_result.get("command", "None"),
                ":verified":           str(verification.get("verified", False)),
                ":reasoning":          analysis.get("reasoning", "None"),
                ":escalate":           str(analysis.get("escalate", False)),
                ":completed_at":       datetime.now(timezone.utc).isoformat()
            }
        )
        logger.info(f"Audit trail written: {incident_id}")
    except Exception as e:
        logger.error(f"Audit trail failed: {e}")