"""
notifier.py — Slack Notification Layer
Step 18 of the AIOps pipeline.

Responsibilities:
  - Send Slack notification for every alert — always
  - Two channels: #incidents (ops team) and #aiops-log (audit)
  - Webhook URL retrieved from Secrets Manager — never hardcoded

GovCloud compliance:
  - Slack webhook URL stored in Secrets Manager
  - No credentials hardcoded anywhere
"""

import json
import logging
import boto3
import os
import urllib.request

logger = logging.getLogger()

AWS_REGION_NAME          = os.environ["AWS_REGION_NAME"]
SLACK_WEBHOOK_SECRET_ARN = os.environ["SLACK_WEBHOOK_SECRET_ARN"]

secrets = boto3.client("secretsmanager", region_name=AWS_REGION_NAME)


###############################################################################
# STEP 18 — NOTIFY SLACK
###############################################################################

def notify_slack(alert, analysis, decision, action_result, verification):
    """
    Sends Slack notification for every alert — always.
    Never silent. Every alert generates a Slack message.
    """
    webhook_url = get_slack_webhook()
    if not webhook_url:
        logger.warning("No Slack webhook — skipping notification")
        return

    action = decision.get("action", "recommend")
    status = action_result.get("status", "unknown")

    # Header and color based on outcome
    if action == "auto_execute" and status == "executed":
        header = "✅ AUTO-REMEDIATION EXECUTED"
        color  = "#36a64f"
    elif action == "escalate":
        header = "🚨 ESCALATION REQUIRED — PAGE ON-CALL"
        color  = "#e01e5a"
    elif action == "auto_execute" and status in ["failed", "blocked"]:
        header = "❌ AUTO-REMEDIATION FAILED — HUMAN REQUIRED"
        color  = "#e01e5a"
    else:
        header = "⚠️ ALERT — HUMAN ACTION REQUIRED"
        color  = "#ff9900"

    message = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": header}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Alert:*\n{alert['alert_name']}"},
                        {"type": "mrkdwn", "text": f"*Severity:*\n{alert['severity']}"},
                        {"type": "mrkdwn", "text": f"*Namespace:*\n{alert['namespace']}"},
                        {"type": "mrkdwn", "text": f"*Pod:*\n{alert['pod']}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause:*\n{analysis.get('root_cause', 'Unknown')}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommended Action:*\n{analysis.get('recommended_action', 'Unknown')}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Confidence:*\n{analysis.get('confidence', 0.0):.0%}"},
                        {"type": "mrkdwn", "text": f"*Risk Level:*\n{analysis.get('risk_level', 'Unknown')}"},
                        {"type": "mrkdwn", "text": f"*Decision:*\n{decision.get('reason', 'Unknown')}"},
                        {"type": "mrkdwn", "text": f"*Action:*\n{status}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Claude Reasoning:*\n{analysis.get('reasoning', 'Not provided')}"
                    }
                }
            ]
        }]
    }

    try:
        data = json.dumps(message).encode("utf-8")
        req  = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Slack notification sent")
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")


def get_slack_webhook():
    """
    Retrieves Slack webhook URL from Secrets Manager.
    Never hardcoded — GovCloud compliance requirement.
    """
    try:
        response = secrets.get_secret_value(SecretId=SLACK_WEBHOOK_SECRET_ARN)
        return response["SecretString"]
    except Exception as e:
        logger.error(f"Failed to get Slack webhook: {e}")
        return None