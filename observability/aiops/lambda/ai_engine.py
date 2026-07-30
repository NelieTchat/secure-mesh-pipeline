"""
ai_engine.py — Bedrock/Claude Integration
Steps 12, 13 of the AIOps pipeline.

Responsibilities:
  - Build controlled AI prompt with all gathered context
  - Call Amazon Bedrock (Claude model)
  - Return structured JSON analysis

GovCloud compliance:
  - IAM role authentication — no API keys
  - All Bedrock invocations logged to CloudTrail automatically
"""

import json
import logging
import boto3
import os
from utils import safe_default

logger = logging.getLogger()

BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
AWS_REGION_NAME  = os.environ["AWS_REGION_NAME"]

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION_NAME)


###############################################################################
# STEP 12 — BUILD PROMPT
###############################################################################

def build_prompt(alert, k8s_context, recent_logs, history, runbook, biz_context, correlation):
    """
    Constructs a controlled AI prompt with all context.
    Every piece of context collected in steps 6-11 feeds into this prompt.
    The prompt constrains Claude to return a specific JSON structure.
    """
    runbook_section = ""
    if runbook["found"]:
        runbook_section = f"""
Approved runbook for this alert type:
{runbook['content']}
"""

    log_section = "\n".join(recent_logs[-20:]) if recent_logs else "No logs available"

    return f"""You are an SRE assistant analyzing a Kubernetes alert.
You must respond ONLY with a valid JSON object.
No explanation, no preamble, no markdown — only the JSON.

ALERT DETAILS:
- Alert name: {alert['alert_name']}
- Severity: {alert['severity']}
- Namespace: {alert['namespace']}
- Pod: {alert['pod']}
- Service: {alert['service']}
- Summary: {alert['summary']}
- Description: {alert['description']}

INCIDENT HISTORY:
- Times this alert has fired: {history['count']}
- Is recurring problem: {history['is_recurring']}
- Last occurred: {history['last_occurred']}

CLUSTER CONTEXT:
- Cluster: {k8s_context['cluster']}
- Current pod status: {k8s_context['status']}

RECENT POD LOGS:
{log_section}

BUSINESS CONTEXT:
- Environment: {biz_context['environment']}
- Current time (UTC): {biz_context['current_time']}
- Off-hours: {biz_context['is_off_hours']}
- Weekend: {biz_context['is_weekend']}
- Production: {biz_context['is_production']}

ALERT CORRELATION:
- Related alerts: {', '.join(correlation['related_alerts']) or 'None'}
- Alert storm detected: {correlation['is_alert_storm']}
{runbook_section}

Respond with this exact JSON structure:
{{
  "root_cause": "specific analysis of what is causing this alert",
  "recommended_action": "specific remediation step with exact commands",
  "confidence": 0.0,
  "risk_level": "LOW|MEDIUM|HIGH",
  "auto_executable": true,
  "kubectl_command": "kubectl rollout restart deployment/name -n namespace",
  "reasoning": "brief explanation of your confidence and risk assessment",
  "escalate": false,
  "escalation_reason": null
}}

Rules:
- confidence: float 0.0 to 1.0
- risk_level: LOW only for pod restart or temporary scale. MEDIUM for config changes. HIGH for data, networking, or unknown issues.
- auto_executable: true ONLY for pod restart or replica scale
- kubectl_command: required if auto_executable is true, otherwise null
- escalate: true if this requires immediate human escalation
- If recurring more than 3 times: increase risk_level and set escalate to true
- If production environment: increase risk_level by one level
"""


###############################################################################
# STEP 13 — CALL BEDROCK
###############################################################################

def call_bedrock(prompt):
    """
    Invokes Claude via Amazon Bedrock.
    GovCloud: all invocations automatically logged to CloudTrail.
    Authentication via IAM role — no API keys anywhere.
    """
    logger.info(f"Calling Bedrock: {BEDROCK_MODEL_ID}")

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            })
        )

        body     = json.loads(response["body"].read())
        raw_text = body["content"][0]["text"].strip()

        return json.loads(raw_text)

    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {e}")
        return safe_default(f"Invalid JSON from Claude: {e}")
    except Exception as e:
        logger.error(f"Bedrock call failed: {e}")
        return safe_default(str(e))