# ISMS API

Base: `/api/v1`. Production requires `Authorization: Bearer <administrator token>` for every API operation. The token comes from the stack's `AdminSecretArn` secret. The root and `/health` are public liveness metadata. `/demo/health` is a public simulation endpoint only when enabled. `/health` is not a database readiness guarantee.

| Method | Route | Behavior |
|---|---|---|
| GET / POST | `/services` | List / register services |
| GET / PUT / DELETE | `/services/{id}` | Read / validate configuration update / remove |
| GET | `/monitoring/{id}/records?hours=24&limit=100` | Newest-first observations; hours optional, bounded limit |
| GET | `/monitoring/{id}/latest` | Latest persisted observation |
| POST | `/monitoring/{id}/check-now` | Actual HTTP probe and deterministic incident processing |
| GET | `/monitoring/{id}/reliability?hours=24` | Probe statistics, percentiles, SLO and completed incident reliability |
| GET | `/monitoring/summary/all` | Latest observation by service |
| GET | `/metrics/overview` | Latest-probe system summary, including unknown services |
| GET | `/incidents?status_filter=INVESTIGATING&service_id=...` | Bounded incident results |
| GET / PATCH | `/incidents/{id}` | Detail with persisted AI / validated operator transition |
| GET | `/incidents/{id}/correlation` | Monitoring/lifecycle timeline and dependency hypotheses |
| POST | `/incidents/{id}/remediate` | Allowlisted, explicitly authorized runbook |
| POST | `/ai/analyze-incident` | Real provider investigation of incident evidence |
| POST | `/ai/chat` | Tool retrieval, Groq fact selection and unconfirmed investigation |
| POST | `/ai/retrain/{id}` | Train on real historical data; 409 for insufficient/invalid candidate |
| GET | `/ai/models/{id}` | Active metadata or explicit no-model state |
| GET | `/ai/analyses?service_id=...` | Persisted investigations |
| GET | `/dependencies` | Declared relationships and transitive affected services |
| GET | `/notifications/status` | Configuration, confirmed and pending email subscription counts |
| PUT | `/demo/mode` | Change actual demo response; requires enabled demo and authorization |

Registration example:

```json
{"service_name":"Payments","url":"https://example.com/health","http_method":"GET","timeout":3,"check_interval":60,"response_time_threshold":1000,"failure_threshold":3,"recovery_threshold":2,"criticality":"critical","dependencies":[],"availability_target":99.9,"latency_target_ms":500,"error_rate_target":0.01}
```

Only GET and HEAD probes are accepted. URLs must exclude credentials/fragments and resolve to public addresses. Probes pin the validated address, verify TLS and do not follow redirects. Private targets are an explicit development-only opt-in.

Acknowledgement: `PATCH /incidents/{id}` with `{"status":"ACKNOWLEDGED","resolution_notes":"Reviewing service logs"}`. Actor comes from authentication, never an arbitrary request field. Allowed operator states are ACKNOWLEDGED, INVESTIGATING, MITIGATING and CLOSED after resolution. Manual resolution of an unverified outage returns 409.

Runbook: `{"action":"retry_health_check","authorized":true,"comments":"Approved probe retry"}`. Other actions: `mute_alerts` (one hour) and `unmute_alerts`. No shell commands, model-generated function names or arbitrary Lambda targets are accepted.

Chat: `{"query":"Which services had the most failures in the last 24 hours?","service_id":null,"incident_id":null}`. The response contains answer, source IDs and provider. Measurements are rendered from backend facts; unknown fact references return 502. No fabricated metrics are substituted on provider failure (503).

Demo modes: ONLINE, HTTP_500, HTTP_503, TIMEOUT, SLOW_RESPONSE, RECOVERY. Slow mode delays two seconds; timeout mode delays fifteen seconds. Configure probe timeout three seconds and latency threshold 500 ms for demonstrations.

Queries intentionally cap data: metrics 3000 observations in reliability/tool windows, service incidents 200, global incident scans at most 50 pages of 200 evaluated items. Truncation/limits mean counts can be lower bounds. These APIs are suitable for a small student deployment; they do not assert unlimited historical completeness.
