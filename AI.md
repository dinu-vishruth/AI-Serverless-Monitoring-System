# Evidence-based AI

Groq uses the configured OpenAI-compatible client and `GROQ_MODEL` (default `openai/gpt-oss-120b`). There are no production mock responses. OpenAI and Bedrock remain optional existing adapters; cloud IAM is configured for Groq. A Groq secret ARN is preferred; deployment can create a managed secret from the NoEcho key parameter. Credentials are not placed in Lambda environment values.

Incident evidence includes the incident snapshot, severity, detector provenance/model version, real recent observations, prior incidents within a correlation window, dependency status, and a timestamped health-check/lifecycle timeline. The system explicitly identifies missing application logs, deployment events and database telemetry. It does not pretend those sources are connected.

The prompt separates observed facts, possible causes, impact and investigation. Structured responses are validated and bounded. Output includes summary, facts, possible causes, impact, actions, next diagnostic checks and confidence. Causes remain hypotheses. Malformed/provider-unavailable results are explicitly marked `analysis_status=unavailable`; any deterministic assessment is labeled rule-based and is never presented as Groq inference.

The incident stream worker sends the alert independently of AI completion. A provider outage cannot suppress incident creation. Groq/OpenAI calls have a twelve-second timeout, one SDK retry and bounded output tokens. Analysis persistence errors are logged as platform failures. Manual reanalysis is available; the worker investigates once per new incident, limiting cost.

The assistant retrieves read-only tools before inference: service status, recent metrics, incidents/history, anomalies, dependencies and recent failures. Retrieval windows are 24 hours or seven days, with calendar-day/week boundaries in UTC for today/this-week questions and explicit caps. Backend facts contain actual counts, rankings, percentiles and provenance. Groq selects relevant fact IDs and proposes hypotheses/diagnostics. The response renderer accepts only known factual IDs and renders all numerical measurements from backend data; numeric assertions in generated prose are discarded. Unknown references fail visibly rather than becoming invented metrics. A missing model is explicitly not assessed.

Service names/evidence are untrusted prompt data. The AI cannot execute commands or choose arbitrary actions. Remediation requires an authenticated operator and the predefined runbook API.

Live local Groq verification was performed during this upgrade. This proves real provider invocation and local orchestration, not production IAM, stream delivery or email receipt. Automated tests use explicit provider mocks and do not count them as live AI tests.

References: [Groq structured output behavior](https://console.groq.com/docs/structured-outputs), [Groq API reference](https://console.groq.com/docs/api-reference).
