# Verification and acceptance

Verified locally on 2026-11-09. Local evidence is distinct from deployed AWS evidence.

## Automated suite

**54 tests passed** in the Linux Python 3.11 runtime with the pinned deployment dependencies. There is one upstream TestClient/httpx deprecation warning; it is not a test failure.

```powershell
docker build -f Dockerfile.test -t isms-test .
docker run --rm isms-test
```

Or with Python 3.11 and installed dependencies:

```powershell
python -m pip install -r backend/requirements-lambda.txt pytest pytest-asyncio "moto[dynamodb,sns,s3,secretsmanager]"
python -m pytest -q
```

Tests isolate storage and settings in temporary directories and never use developer credentials or existing telemetry. Running the legacy `unittest discover` command does not activate pytest's isolation fixture; use pytest for this suite.

Coverage includes service CRUD, authentication/CORS, actual HTTP status and network failure classification, risk scoring, feature preparation, real Isolation Forest fitting/inference, no-fake-sample retraining, S3 cold-cache loading, failed candidate preservation, incident hysteresis/dedup/replay/acknowledgement/relapse/recovery, DynamoDB conditional writes and TTL, dependency cycles/blast radius, insufficient-data statistics, percentiles, approved runbooks, AI grounding and SNS lifecycle behavior.

`test_end_to_end.py` starts a real local HTTP server, collects actual baseline observations, trains a real model, introduces latency and HTTP failures, verifies one incident and administrator acknowledgement, then verifies recovery and notification history. Groq/SNS are explicitly mocked in this automated scenario. It proves orchestration, not provider availability or inbox delivery. The deterministic recovery section removes the test model pointer to isolate hysteresis from intentionally noisy model scoring; S3/inference behavior has separate tests.

## Live local demonstration

`python scripts/demo.py --require-ai` was run against the local backend with actual Groq inference. Observed: initial HTTP 200; first two HTTP 503 samples suspected; third creates one incident; later failures reuse its ID; authenticated/local-operator acknowledgement persists; actual Groq investigation and assistant respond; first clean sample enters recovery pending; second resolves.

The grounded assistant rendered four failed probes out of five retrieved probes and explicitly reported `no_model` as not assessed. This demonstration intentionally did not claim ML predicted the HTTP outage. The automated ML tests separately exercise actual trained inference.

All six actual simulator responses were also exercised locally: ONLINE 200, HTTP_500 500, HTTP_503 503, client-observed TIMEOUT, two-second SLOW_RESPONSE, and RECOVERY 200.

Local SNS was unconfigured: subscription count zero and email delivery unverified. No local mock or successful provider call is counted as email proof.

## Build and dependency checks

Frontend: `npm run build` succeeds with Vite 7.3.7 / React plugin 5.2.0. Node requires 20.19+ or 22.12+. `npm audit` reports zero known vulnerabilities after updating the existing vulnerable toolchain.

Backend: `pip-audit` on the final isolated image reports no known vulnerabilities. Initial findings in the pinned web/dotenv dependencies and base image packaging tools were corrected. Audits are a snapshot of published advisories, not a guarantee against undiscovered vulnerabilities.

SAM: `sam validate --lint --region ap-south-2` succeeds. Linux container SAM builds succeed using `scripts/prepare_build.py` and `--base-dir .build-source` on this workstation. The layer builder excludes upstream tests/caches and unused AWS service definitions, caps the layer below 235 MiB, and enforces a combined 240 MiB budget. All five Lambda artifacts match all 47 deployable Python source files; each combined package is 234.46 MiB. The actual pruned artifacts construct every retained AWS SDK client, import FastAPI/pandas/scikit-learn, and perform real Isolation Forest inference in the AWS Python 3.11 build runtime. A required NumPy runtime helper under its tests directory is retained.

## Live AWS acceptance — 2026-11-09

The existing `intelligent-serverless-monitoring` stack in `ap-south-2` reached `UPDATE_COMPLETE`, preserving the API endpoint and all four data tables. Existing API/health-checker log groups were imported and retained. Deployment exposed a legacy bundled-code/new-layer overlap, resolved by creating replacement functions with stable names. A missing model-bucket `ListBucket` permission was also found and fixed; missing models now return `no_model` rather than `inference_failed`.

Verified against `https://8adg3z8xce.execute-api.ap-south-2.amazonaws.com`:

- Unauthenticated API requests return 401; the Secrets Manager administrator token permits authenticated access. The dashboard preview origin passes CORS preflight.
- Actual HTTP 200 -> repeated 503 -> one incident -> authenticated acknowledgement -> recovery pending -> resolution. Incident `INC-c83f4b9550d8bde2301d` received actual Groq investigation and a grounded assistant response using `openai/gpt-oss-120b`.
- The incident stream worker published real SNS creation and recovery messages (`dbb80023-d707-58ea-b205-634800e86a7b` and `7d61fdd2-e194-5f40-b414-9eb9366d020e`). These prove SNS acceptance, not inbox delivery.
- EventBridge generated a healthy observation at `2026-11-09T14:17:22.665277+00:00` before any manual probe of the acceptance service.
- Additional actual cloud probes classified HTTP 500, a roughly 2.09-second slow response, a roughly 3.06-second timeout, and subsequent HTTP 200 recovery. The target is warmed before measuring recovery after a timed-out invocation; its cold initialization can exceed the configured probe timeout.
- Twenty-five manual healthy observations plus the scheduled observation trained a real model on 26 samples. Version `20261109T141952-26ae16fda3ef` and its active pointer were verified in S3. Chronological evaluation used 20 training and six validation samples; this is an unlabeled evaluation, not measured predictive accuracy.
- A newly published health-checker version `1` loaded that model from S3 in a fresh Lambda environment and recorded `ml_status=predicted` with the matching version. Invocation `8fcdc641-95f7-411c-a0b3-6d4037522be5` reported a 6.32-second initialization and 337 MB maximum memory use. Its HTTP 200 sample was scored anomalous; this is an unusual observation, not a predicted outage.
- The stream mapping was enabled with processing result `OK`; the failure queue had zero visible and in-flight messages. Post-fix acceptance logs contained no platform errors. The platform alarm detected the earlier IAM errors; metric filters now emit zero on healthy traffic, and the alarm subsequently recovered. All six deployed alarms finished in `OK`.

Temporary verification services were removed and the demo endpoint restored to ONLINE. Model artifacts and the verification Lambda version remain available for audit. The frontend production build targets the deployed API and is served locally at `http://127.0.0.1:3001`; HTTP delivery was checked.

## Not verified in this session

The SNS topic has zero email subscriptions. Subscription confirmation and actual creation/recovery inbox receipt remain pending an alert address and confirmation. Deliberate discarded-event delivery to SQS and the next daily training schedule occurrence were not exercised. Public frontend hosting remains unconfigured.

The browser skill initialized but returned no available in-app browser (`agent.browsers.list()` was empty). The backend and frontend were started and HTTP/API behavior was exercised, but no visual/browser interaction acceptance is claimed.

The GitHub Actions workflow runs tests, frontend build, SAM validation and SAM build. It has been added but has not executed on GitHub in this session. All cloud acceptance steps are in DEPLOYMENT.md and OPERATIONS.md.
