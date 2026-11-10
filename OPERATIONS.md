# Operations and demonstration

Start backend and frontend using README. The dashboard reports stale/failing fetches, active incidents, lifecycle actions, dependency edges, affected-service counts, recovery duration, real model metadata and per-service reliability. The dependency graph uses administrator-declared service IDs; correlated failures are possible explanations, not proven causes.

Enable the local demo with `DEMO_ENABLED=true` and `ALLOW_PRIVATE_TARGETS=true` in development only. In AWS deploy `EnableDemo=true`; stack output `DemoHealthEndpoint` is the public HTTPS target. Register it with three-second timeout, 500 ms latency threshold, failure threshold three and recovery threshold two. Cloud scheduling checks services no more frequently than once per minute; longer configured intervals are respected.

1. Set ONLINE; run a probe. Availability for one successful observation is 100% of measured probes, not an SLA guarantee.
2. Collect at least 20 real observations and retrain if demonstrating ML. Model metadata must show an active version. Set SLOW_RESPONSE; inspect response time, anomaly score/provenance and sustained degradation. Do not claim that every slow sample is necessarily an ML anomaly.
3. Set HTTP_503. Three failed checks confirm one incident. Further failures update that incident. Inspect its timeline and actual Groq analysis.
4. Confirm the SNS email subscription and inspect notification history. SNS publish success proves acceptance, not inbox delivery; inspect the actual email separately.
5. Acknowledge, investigate and mitigate through the dashboard. Use an explicitly approved retry runbook if desired. Every runbook records actor, time, action and result.
6. Set RECOVERY. One clean check enters recovery pending; the next clean check resolves the incident and records detection-based downtime. A failed recovery returns to the same incident.
7. Ask the assistant why the service failed, which services are unhealthy, or which had the highest measured failure count. Observe source IDs and confirmed measurements separately from hypotheses.

For an automated real-provider demonstration:

```powershell
python scripts/demo.py --base-url http://127.0.0.1:8001 --require-ai
```

For cloud, set `ISMS_ADMIN_TOKEN` privately in the process environment and use the stack API endpoint as base URL. This script registers a temporary service, exercises actual probes and Groq, verifies acknowledgement/dedup/recovery, restores ONLINE and removes its service registration. Incident evidence remains for audit. It does not confirm email receipt or demonstrate EventBridge scheduling; separately wait for a scheduled observation and check CloudWatch.

Notifications: one created event, a critical severity update if applicable, one escalation after fifteen minutes of unresolved failure, and recovery. No repeated minute-by-minute emails. Per-incident muting lasts one hour and does not suppress recovery. Every publish attempt is recorded; SDK retries use exponential backoff. Stream failures are retried and eventually retained in the failure queue. SNS Standard is at least once: a crash after publication before persistence can duplicate a message.

Reliability: availability/error budget are probe-sample based; latency excludes failed requests. P50 needs two successful probes, P95 twenty, P99 one hundred. Missing coverage and insufficient data are unknown. MTTR uses completed incident durations and MTBF fully observed recovery-to-next-incident intervals. These are observed-window statistics, not contractual SLA certification.

Platform failures are distinct from target failures. Review CloudWatch Lambda errors, custom platform-failure metrics and the pipeline queue alarm. Liveness alone does not establish DynamoDB/Groq/SNS readiness. For failed stream records inspect the SQS failure envelope, repair the dependency/IAM issue, then replay incident IDs to the analyzer with care; email delivery may be duplicated.

Troubleshooting: 401 means missing/incorrect admin token; 409 retrain means insufficient/rejected data; 409 transition means recovery is not verified; 502 assistant means unsupported model evidence; 503 means provider/platform unavailable. Check SNS pending confirmations before diagnosing email failure. For model mismatch retrain using the deployed pinned runtime. For local Windows native module policy failures use the documented Docker runtime.
