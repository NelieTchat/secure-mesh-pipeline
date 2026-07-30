"""
policy.py — Safety Policy Engine
Step 15 of the AIOps pipeline.

Responsibilities:
  - Apply deterministic graduated automation rules
  - Override Claude when safety rules require it
  - This is NOT AI — this is hard policy that overrides Claude

Decision matrix:
  Escalate flag set                        → page on-call
  Production environment                   → recommend only
  HIGH risk (any confidence)               → never auto-execute
  LOW confidence < 0.85                    → recommend only
  Not auto_executable per Claude           → recommend only
  LOW risk + HIGH confidence + off-hours   → auto-execute
  LOW risk + HIGH confidence + biz hours   → recommend with approval
  MEDIUM risk (any time)                   → recommend only
"""

import logging

logger = logging.getLogger()

CONFIDENCE_THRESHOLD = 0.85


###############################################################################
# STEP 15 — APPLY SAFETY POLICY
###############################################################################

def apply_safety_policy(analysis, biz_context):
    """
    Applies deterministic graduated automation rules.
    Claude recommends. This function decides.
    Hard rules — cannot be overridden by AI output.
    """
    confidence      = analysis.get("confidence", 0.0)
    risk_level      = analysis.get("risk_level", "HIGH")
    auto_executable = analysis.get("auto_executable", False)
    escalate        = analysis.get("escalate", False)
    is_off_hours    = biz_context["is_off_hours"]
    is_production   = biz_context["is_production"]
    current_hour    = biz_context["current_hour"]

    # Escalation overrides everything
    if escalate:
        return {
            "action":        "escalate",
            "reason":        analysis.get("escalation_reason", "Claude flagged for escalation"),
            "auto_executed": False
        }

    # Production — never auto-execute
    if is_production:
        return {
            "action":        "recommend",
            "reason":        "Production environment — human approval required",
            "auto_executed": False
        }

    # HIGH risk — never auto-execute
    if risk_level == "HIGH":
        return {
            "action":        "recommend",
            "reason":        "HIGH risk — human approval required",
            "auto_executed": False
        }

    # LOW confidence — recommend only
    if confidence < CONFIDENCE_THRESHOLD:
        return {
            "action":        "recommend",
            "reason":        f"Confidence {confidence:.0%} below threshold {CONFIDENCE_THRESHOLD:.0%}",
            "auto_executed": False
        }

    # Claude says not auto-executable
    if not auto_executable:
        return {
            "action":        "recommend",
            "reason":        "Action requires manifest change or human judgment",
            "auto_executed": False
        }

    # MEDIUM risk — recommend only
    if risk_level == "MEDIUM":
        return {
            "action":        "recommend",
            "reason":        "MEDIUM risk — human approval recommended",
            "auto_executed": False
        }

    # LOW risk + HIGH confidence + off-hours → auto-execute
    if risk_level == "LOW" and is_off_hours:
        return {
            "action":        "auto_execute",
            "reason":        f"HIGH confidence + LOW risk + off-hours ({current_hour:02d}:00 UTC)",
            "auto_executed": True
        }

    # LOW risk + HIGH confidence + business hours → recommend with approval
    return {
        "action":        "recommend",
        "reason":        f"HIGH confidence + LOW risk but business hours ({current_hour:02d}:00 UTC)",
        "auto_executed": False
    }