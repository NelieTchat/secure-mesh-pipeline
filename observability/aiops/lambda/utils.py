"""
utils.py — Shared utilities
Used by all modules in the AIOps Lambda pipeline.
"""

import json
import logging

logger = logging.getLogger()


def response(status_code, body):
    """Standard API Gateway response format."""
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body)
    }


def safe_default(reason):
    """
    Returns a safe fallback analysis when Claude cannot be reached.
    Always HIGH risk, never auto-executable.
    Human review required — never fails silently.
    """
    logger.error(f"Using safe default: {reason}")
    return {
        "root_cause":         f"Analysis unavailable: {reason}",
        "recommended_action": "Manual investigation required",
        "confidence":         0.0,
        "risk_level":         "HIGH",
        "auto_executable":    False,
        "kubectl_command":    None,
        "reasoning":          "Fallback — Claude unavailable",
        "escalate":           True,
        "escalation_reason":  reason
    }