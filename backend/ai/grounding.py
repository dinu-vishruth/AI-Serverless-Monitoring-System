"""Render factual assistant statements exclusively from retrieved tool results."""
import re


def build_facts(context):
    facts = {}
    def add(text):
        facts[f"fact-{len(facts)+1}"] = text
    operational = context.get("operational_data", {})
    window = operational.get("requested_window_hours", 24)
    add(f"Data retrieved at {operational.get('as_of', 'unknown')}; requested window: {operational.get('window_label', f'last {window} hours')}. Counts may be bounded by retrieval limits.")
    prefix = "at least " if operational.get("global_incident_count_is_lower_bound") else ""
    add(f"System-wide incidents in {operational.get('window_label', 'retrieved window')}: {prefix}{operational.get('global_incident_count', 0)}. This includes retained incidents for deleted services.")
    for service in context.get("services", []):
        latest = service.get("latest_telemetry")
        name = service.get("service_name") or service.get("service_id")
        if latest:
            add(f"{name}: latest check {latest.get('timestamp')}; HTTP {latest.get('status_code')}; response {latest.get('response_time')} ms; probe availability {latest.get('availability')}; ML status {latest.get('ml_status', 'not evaluated')}. No model means ML made no assessment.")
        else:
            add(f"{name}: no monitoring evidence is available; health is unknown.")
    for service in operational.get("services", []):
        stats = service["reliability"]
        count_prefix = "at least " if service.get("incident_count_is_lower_bound") else ""
        add(f"{service.get('service_name')}: {stats['failure_count']} failed probes out of {stats['sample_count']} retrieved probes; observed availability {stats['availability_percentage']} percent; error rate {stats['error_rate']}; window incidents {count_prefix}{service['incident_count']}. These are probe statistics, not customer request metrics.")
        add(f"{service.get('service_name')}: average successful-probe latency {stats['average_latency_ms']} ms; P95 {stats['p95_ms']} ms; latency trend {stats['latency_trend_ms']} ms. Null means insufficient observations.")
    ranked = sorted(operational.get("services", []), key=lambda s: s['reliability']['failure_count'], reverse=True)
    if ranked:
        top = ranked[0]['reliability']['failure_count']
        winners = [s.get('service_name') for s in ranked if s['reliability']['failure_count'] == top]
        add(f"Highest observed failure count in retrieved window: {', '.join(winners)}, {top} failures each. Ranking is limited to the retrieved services and samples.")
    for incident in context.get("incidents", []):
        add(f"Incident {incident['incident_id']}: service {incident.get('service_name')}; status {incident.get('status')}; severity {incident.get('severity')}; created {incident.get('created_at')}; trigger {incident.get('trigger_reason')}. Exact root cause is unconfirmed by health checks alone.")
    return facts


def render_answer(response, facts):
    if not isinstance(response, dict): raise ValueError("Assistant response must be an object")
    references = response.get("fact_ids", [])
    if not isinstance(references, list) or not references or any(not isinstance(ref, str) or ref not in facts for ref in references):
        raise ValueError("Assistant referenced unsupported facts")
    lines = ["Observed application evidence:"] + [f"- {facts[ref]}" for ref in dict.fromkeys(references)]
    for field, title in (("possible_causes", "Possible causes — unconfirmed"), ("recommended_actions", "Recommended investigation")):
        values = response.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values): raise ValueError("Invalid assistant investigation fields")
        # LLM-generated prose must not introduce quantities. Measurements and
        # counts are accepted only through the whitelisted factual statements.
        values = [v[:800] for v in values[:6] if not re.search(r"\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|percent|confirmed|definitely|certainly)\b", v, re.I)]
        if values:
            lines += ["", title + ":"] + [f"- {v}" for v in values]
    return "\n".join(lines)
