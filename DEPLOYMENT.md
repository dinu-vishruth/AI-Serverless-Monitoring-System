# AWS deployment — ap-south-2

Use AWS CLI credentials with permission to update the existing ISMS stack, create scoped IAM roles, and deploy its managed resources. Reauthenticate with `aws login` when a session expires. The existing `intelligent-serverless-monitoring` stack was successfully upgraded in this session; cloud evidence is recorded in TESTING.md. Do not log keys, export credentials into source, or commit samconfig secrets.

## Validate and build

```powershell
sam validate --lint --region ap-south-2
sam build --use-container --region ap-south-2
python scripts/verify_build.py
```

Docker builds Linux Python 3.11 native scientific dependencies. A shared layer uses `backend/requirements-lambda.txt`; its builder excludes upstream tests/cache files and unused AWS service models, caps the layer below 235 MiB, and verifies SDK client construction plus real model inference. Combined artifacts must remain below 240 MiB to leave deployment headroom. Function artifacts include backend code only, never the repository's `.env`, local database, node_modules or virtual environments.

For this workstation's existing nested `backend/venv`, stage only deployable sources to avoid copying that environment into SAM's build scratch space:

```powershell
python scripts/prepare_build.py
sam build --use-container --base-dir .build-source --region ap-south-2
```

This is a local optimization. Clean checkouts and CI do not need it.

## Deploy

```powershell
sam deploy --guided --region ap-south-2
```

Use the existing stack name when upgrading: the original fixed names Services, MonitoringData, Incidents, AIAnalysis and SNS topic are retained for compatibility. Do not deploy a second stack against tables owned by another stack. Review the change set: this upgrade adds incident streams, model storage, a shared runtime layer, failure handling, secrets, alarms, and optional demo/email resources. Database key schemas are preserved.

Parameters:

| Parameter | Meaning |
|---|---|
| GroqSecretArn | Preferred: existing secret with plain key or JSON `api_key` |
| GroqApiKey | Optional NoEcho migration input; SAM stores it in a managed secret, not Lambda environment values |
| AlertEmail | Optional recipient; AWS sends a subscription confirmation email |
| CorsOrigins | Exact dashboard origins, comma separated; include localhost if using a local dashboard |
| EnableDemo | `true` creates the dedicated failure simulation Lambda/public health route |
| WorkerReservedConcurrency | Reservation for each scheduled worker; default `0` omits reservations for small-quota accounts. Set only when the regional quota leaves AWS's required unreserved capacity. Service leases still serialize health checks. |

When upgrading an existing stack, inspect its Lambda log groups before deploying. If the health-checker or API log group already exists outside CloudFormation, import it into the existing stack as `HealthCheckerFunctionLogGroup` or `ApiFunctionLogGroup` using an import-only change set based on the current original template. Preserve the exact log-group name and use `DeletionPolicy: Retain`; execute the application update only after the import completes. The upgrade then applies 14-day retention without deleting the existing group.

Preserve previous stack parameters explicitly with `UsePreviousValue` during an import. When the imported template uses literal log-group names, run `python scripts/prepare_cloud_template.py --stack-name intelligent-serverless-monitoring` after building, then package/deploy `.aws-sam/build/template.yaml`. This preserves those names and routes the replacement functions to those retained logs. Review the change set before execution; existing tables, API, and imported log groups should not require replacement.

The migration gives the four workers/API functions explicit names. This intentionally replaces legacy functions whose ZIPs bundled scientific dependencies. An in-place update can attach the new layer before replacing that old ZIP, temporarily exceeding Lambda's combined size limit even when the final artifacts fit. Creating the replacement functions installs the slim code and layer together; CloudFormation then switches the existing API and schedule permissions. Later deployments reuse these stable function names.

The generated AdminSecret is mandatory for production API access. Retrieve it privately using the stack output AdminSecretArn and Secrets Manager, then paste its value into the dashboard access field. Do not put this token in VITE build settings or checked-in files. The shared token identifies a single administrator role; individual user accounts/RBAC are not included.

On Windows, copy the token directly to the clipboard without printing it in chat or terminal output:

```powershell
$ismsAdminArn = aws cloudformation describe-stacks --stack-name intelligent-serverless-monitoring --region ap-south-2 --query "Stacks[0].Outputs[?OutputKey=='AdminSecretArn'].OutputValue | [0]" --output text
$ismsAdminValue = aws secretsmanager get-secret-value --secret-id $ismsAdminArn --region ap-south-2 --query SecretString --output text
Set-Clipboard -Value $ismsAdminValue.Trim()
Remove-Variable ismsAdminValue
```

Open http://127.0.0.1:3001 and paste it into Administrator access. This preview uses the deployed API. Port 3000 is occupied by another application on this workstation. Restart the preview when needed with `npm.cmd run preview -- --host 127.0.0.1 --port 3001 --strictPort` from `frontend` after building with the production API origin.

Outputs include ApiEndpoint, SnsTopicArn, table names, AdminSecretArn, ModelBucketName, FailureQueueUrl and (if enabled) DemoHealthEndpoint. Confirm the SNS email subscription in the inbox. `/api/v1/notifications/status` must report a confirmed email subscriber before expecting email delivery.

## Frontend

The original repository has no managed static-hosting resource. Build the existing frontend for your static host, or run it locally with CORS permitting localhost:

```powershell
$env:VITE_API_ORIGIN = 'https://YOUR_API.execute-api.ap-south-2.amazonaws.com'
cd frontend
npm ci
npm run build
```

Deploy `frontend/dist` to your existing static hosting service. Vite's relative development proxy still targets port 8001; production API origin is configured at build time. Configure the exact deployed dashboard origin in CorsOrigins.

## Acceptance checks after deployment

1. Inspect stack completion and every Lambda's CloudWatch logs.
2. Verify API returns 401 without a token and allows authenticated reads/actions.
3. Register DemoHealthEndpoint with a three-second probe timeout; wait for an actual EventBridge-generated observation.
4. Collect real baseline data, train, inspect versioned S3 metadata, and verify another Lambda cold start loads the model.
5. Exercise slow/503/timeout/recovery modes. Verify one active incident, actual Groq analysis, acknowledgement timeline, repeated clean-check resolution, SNS publish history and actual creation/recovery emails.
6. Inspect platform alarms/failure queue and confirm stream-trigger configuration. Local mocks do not satisfy these checks.

`python scripts/demo.py --base-url <ApiEndpoint> --require-ai` automates the HTTP/incident/Groq/recovery portion using a private `ISMS_ADMIN_TOKEN` process variable. Check actual EventBridge scheduling and inbox delivery separately.

Secrets can be rotated in Secrets Manager; cached readers require a fresh Lambda execution environment after rotation in this version. Old S3 model versions are retained for audit; rollback by restoring a known-good active pointer and matching runtime. Never load third-party joblib artifacts. Disable demo when presentation testing ends. Model storage uses Retain on stack deletion; inventory retained data before cleanup.

