"""
handler.py — Lambda Entry Point & Orchestrator
===============================================
Receives AlertManager webhooks and orchestrates the full
20-step AIOps incident response lifecycle.

Each step is handled by a dedicated module:
  validator.py  — steps 2, 3, 4, 14
  context.py    — steps 6, 7, 8, 9, 10, 11
  ai_engine.py  — steps 12, 13
  policy.py     — step 15
  executor.py   — steps 16, 17
  notifier.py   — step 18
  audit.py      — steps 5, 19
  utils.py      — shared utilities

GovCloud compliance:
  - IAM role authentication — no hardcoded credentials
  - VPC-bound execution — no public internet exposure
  - CloudTrail logs every Bedrock invocation automatically
  - KMS-encrypted environment variables
  - All automated actions logged with timestamp and actor
"""

import json
import logging

from validator import validate_alert, normalize_alert, check_duplicate, validate_ai_response
from context   import gather_k8s_context, gather_recent_logs, get_incident_history, load_runbook, get_business_context, correlate_alerts
from ai_engine import build_prompt, call_bedrock
from policy    import apply_safety_policy
from executor  import execute_action, verify_action
from notifier  import notify_slack
from audit     import create_incident_record, write_audit_trail
from utils     import response

import boto3
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION_NAME     = os.environ["AWS_REGION_NAME"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION_NAME)
table    = dynamodb.Table(DYNAMODB_TABLE_NAME)


###############################################################################
# MAIN HANDLER
###############################################################################

def lambda_handler(event, context):
    """
    Entry point. API Gateway triggers this with AlertManager payload.
    """
    logger.info("AIOps handler triggered")

    try:
        body   = json.loads(event.get("body", "{}"))
        alerts = body.get("alerts", [])

        if not alerts:
            logger.info("No alerts in payload")
            return response(200, {"message": "No alerts to process"})

        results = []
        for alert in alerts:
            result = orchestrate(alert)
            results.append(result)

        return response(200, {"processed": len(results), "results": results})

    except Exception as e:
        logger.error(f"Handler error: {str(e)}")
        return response(500, {"error": str(e)})


###############################################################################
# ORCHESTRATOR
###############################################################################

def orchestrate(alert):
    """
    Runs the full 20-step lifecycle for one alert.
    Each step is a separate function in a dedicated module.
    Clear, testable, auditable.
    """

    # ── Step 1: Receive ───────────────────────────────────────────────────────
    logger.info(f"Step 1 — Received: {alert}")

    # ── Step 2: Validate ──────────────────────────────────────────────────────
    is_valid, validation_error = validate_alert(alert)
    if not is_valid:
        logger.warning(f"Step 2 — Invalid: {validation_error}")
        return {"status": "invalid", "reason": validation_error}

    # ── Step 3: Normalize ─────────────────────────────────────────────────────
    alert = normalize_alert(alert)
    logger.info(f"Step 3 — Normalized: {alert['alert_name']}")

    # ── Step 4: Deduplicate ───────────────────────────────────────────────────
    is_duplicate, incident_id = check_duplicate(alert, table)
    if is_duplicate:
        logger.info(f"Step 4 — Duplicate: {incident_id}")
        return {"status": "duplicate", "incident_id": incident_id}

    # ── Step 5: Create incident record ────────────────────────────────────────
    incident_id = create_incident_record(alert)
    logger.info(f"Step 5 — Incident: {incident_id}")

    # ── Step 6: Kubernetes context ────────────────────────────────────────────
    k8s_context = gather_k8s_context(alert)
    logger.info("Step 6 — K8s context gathered")

    # ── Step 7: Recent logs ───────────────────────────────────────────────────
    recent_logs = gather_recent_logs(alert)
    logger.info(f"Step 7 — Logs: {len(recent_logs)} entries")

    # ── Step 8: Incident history ──────────────────────────────────────────────
    history = get_incident_history(alert["alert_name"], table)
    logger.info(f"Step 8 — History: {history['count']} past incidents")

    # ── Step 9: Load runbook ──────────────────────────────────────────────────
    runbook = load_runbook(alert["alert_name"])
    logger.info(f"Step 9 — Runbook: {runbook['found']}")

    # ── Step 10: Business context ─────────────────────────────────────────────
    biz_context = get_business_context()
    logger.info(f"Step 10 — Business context: off-hours={biz_context['is_off_hours']}")

    # ── Step 11: Correlate alerts ─────────────────────────────────────────────
    correlation = correlate_alerts(alert, history)
    logger.info(f"Step 11 — Correlation: storm={correlation['is_alert_storm']}")

    # ── Step 12: Build prompt ─────────────────────────────────────────────────
    prompt = build_prompt(
        alert, k8s_context, recent_logs,
        history, runbook, biz_context, correlation
    )
    logger.info("Step 12 — Prompt built")

    # ── Step 13: Call Bedrock ─────────────────────────────────────────────────
    analysis = call_bedrock(prompt)
    logger.info("Step 13 — Bedrock response received")

    # ── Step 14: Validate AI response ─────────────────────────────────────────
    analysis = validate_ai_response(analysis)
    logger.info("Step 14 — AI response validated")

    # ── Step 15: Apply safety policy ──────────────────────────────────────────
    decision = apply_safety_policy(analysis, biz_context)
    logger.info(f"Step 15 — Decision: {decision['action']}")

    # ── Step 16: Execute action ───────────────────────────────────────────────
    action_result = execute_action(decision, analysis, alert)
    logger.info(f"Step 16 — Action: {action_result['status']}")

    # ── Step 17: Verify action ────────────────────────────────────────────────
    verification = verify_action(action_result, alert)
    logger.info(f"Step 17 — Verified: {verification['verified']}")

    # ── Step 18: Notify Slack ─────────────────────────────────────────────────
    notify_slack(alert, analysis, decision, action_result, verification)
    logger.info("Step 18 — Slack notified")

    # ── Step 19: Write audit trail ────────────────────────────────────────────
    write_audit_trail(incident_id, alert, analysis, decision, action_result, verification)
    logger.info(f"Step 19 — Audit trail written")

    # ── Step 20: Return ───────────────────────────────────────────────────────
    logger.info(f"Step 20 — Complete: {incident_id}")
    return {
        "incident_id": incident_id,
        "alert":       alert["alert_name"],
        "decision":    decision["action"],
        "status":      action_result["status"]
    }