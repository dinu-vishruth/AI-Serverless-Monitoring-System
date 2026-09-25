"""
AI prompt templates for incident analysis and monitoring assistant.
"""

INCIDENT_ANALYSIS_SYSTEM_PROMPT = """You are an incident analysis assistant for a serverless event monitoring system.

Analyze only the monitoring evidence provided to you.

Do not invent logs, events, metrics, root causes, or system components that are not present in the provided evidence.

Clearly separate:

1. Observed facts
2. Possible causes
3. Impact
4. Recommended investigation steps

If the available evidence is insufficient to identify a root cause, explicitly state:
"The exact root cause cannot be determined from the available monitoring evidence."

Do not claim certainty when the evidence only supports a possibility.

Return structured JSON containing:
{
  "incident_summary": "Brief summary of the incident",
  "observed_facts": ["fact1", "fact2"],
  "possible_causes": ["cause1", "cause2"],
  "impact": ["impact1", "impact2"],
  "recommended_actions": ["action1", "action2"],
  "confidence": "low|medium|high"
}

Only return valid JSON. Do not include any text outside the JSON object."""


MONITORING_ASSISTANT_SYSTEM_PROMPT = """You are an AI monitoring assistant for a serverless event monitoring system.

You help administrators understand the current state of their monitored services.

RULES:
1. Only answer based on the monitoring data provided to you.
2. Never invent monitoring results or claim access to data not provided.
3. If information is unavailable, explicitly state that.
4. Distinguish between facts (from data) and possible explanations (your analysis).
5. Never expose API keys, secrets, or sensitive log information.
6. Do not provide generic answers — only use the actual monitoring data.
7. Keep answers concise and actionable.

When asked about service health, incidents, or anomalies, base your response
entirely on the provided monitoring context."""


def build_incident_analysis_prompt(evidence: dict) -> str:
    """
    Builds the user prompt for incident analysis with structured evidence.

    Args:
        evidence: Dict containing service info, metrics, ML analysis, etc.

    Returns:
        Formatted prompt string.
    """
    import json

    prompt_parts = ["Analyze the following monitoring incident:\n"]

    # Service info
    service = evidence.get("service", "Unknown Service")
    prompt_parts.append(f"Service: {service}\n")

    # Current metrics
    current = evidence.get("current_metrics", {})
    if current:
        prompt_parts.append("Current Metrics:")
        for key, value in current.items():
            prompt_parts.append(f"  - {key}: {value}")
        prompt_parts.append("")

    # Historical baseline
    baseline = evidence.get("historical_baseline", {})
    if baseline:
        prompt_parts.append("Historical Baseline:")
        for key, value in baseline.items():
            prompt_parts.append(f"  - {key}: {value}")
        prompt_parts.append("")

    # ML analysis
    ml = evidence.get("ml_analysis", {})
    if ml:
        prompt_parts.append("ML Analysis:")
        for key, value in ml.items():
            prompt_parts.append(f"  - {key}: {value}")
        prompt_parts.append("")

    # CloudWatch evidence
    cw_evidence = evidence.get("cloudwatch_evidence", [])
    if cw_evidence:
        prompt_parts.append("CloudWatch Evidence:")
        for item in cw_evidence[:10]:  # Limit to 10 items
            prompt_parts.append(f"  - {item}")
        prompt_parts.append("")

    # Trigger reason
    trigger = evidence.get("trigger_reason", "")
    if trigger:
        prompt_parts.append(f"Trigger Reason: {trigger}\n")

    return "\n".join(prompt_parts)


def build_assistant_context_prompt(context: dict) -> str:
    """
    Builds a context prompt for the monitoring assistant with current data.

    Args:
        context: Dict containing services, incidents, analyses.

    Returns:
        Formatted context string.
    """
    import json

    parts = ["Current Monitoring Data:\n"]

    # Services
    services = context.get("services", [])
    if services:
        parts.append(f"Monitored Services ({len(services)}):")
        for svc in services:
            status = "HEALTHY" if svc.get("availability", 1) >= 0.95 else "DEGRADED"
            parts.append(
                f"  - {svc.get('service_name', 'Unknown')} ({svc.get('service_id', '')}): "
                f"Status={status}, RT={svc.get('response_time', 'N/A')}ms, "
                f"ErrorRate={svc.get('error_rate', 0):.2%}"
            )
        parts.append("")

    # Recent incidents
    incidents = context.get("incidents", [])
    if incidents:
        parts.append(f"Recent Incidents ({len(incidents)}):")
        for inc in incidents[:10]:
            parts.append(
                f"  - {inc.get('incident_id', '')}: "
                f"Service={inc.get('service_id', '')}, "
                f"Severity={inc.get('severity', 'UNKNOWN')}, "
                f"Status={inc.get('status', 'UNKNOWN')}, "
                f"Reason={inc.get('trigger_reason', 'N/A')}"
            )
        parts.append("")

    # Recent analyses
    analyses = context.get("analyses", [])
    if analyses:
        parts.append(f"Recent AI Analyses ({len(analyses)}):")
        for a in analyses[:5]:
            parts.append(
                f"  - Service={a.get('service_id', '')}: "
                f"Anomaly={a.get('anomaly', False)}, "
                f"Risk={a.get('risk_level', 'N/A')}, "
                f"Score={a.get('anomaly_score', 0):.2f}"
            )

    return "\n".join(parts)
