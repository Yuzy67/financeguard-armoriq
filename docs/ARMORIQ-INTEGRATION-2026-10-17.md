# ArmorIQ integration evidence — October 17, 2026

## Outcome

Not fixed end to end. The deployed backend can create a real ArmorIQ plan and send
accepted telemetry, but the read-only invocation fails. The existing agent and
policy relationships cannot be verified with the available dashboard access.
No registration, policy, scan, remote setting, push or deployment was changed.

The reproducible, sanitized [trace](evidence/armoriq-trace-2026-10-17.json) contains
no credentials, intent tokens or customer invoice contents.

## Confirmed requests and results

The frontend calls same-origin `/api/...` routes. Vercel hosts the FastAPI backend
in `app.py`; `vercel.json` configures that Python function, not a separate API host.

A fresh synthetic guest session used the same HTTP contract as the frontend:

| Request | Actual result |
| --- | --- |
| `/api/demo`, then `/api/state` | 200; source confirmed as sample |
| `/api/approve`, summary, ArmorIQ engine | 200 APPROVED; actual SDK plan created |
| `/api/run-approved-action` | 502, MCPInvocationException; verified=false; no summary returned |
| `/api/attempt-refund`, same plan | IntentMismatchException; SDK intent binding rejected it before proxy invocation |

Session: `6bf30653-6769-4a8f-bcc8-42b30f0813ca`.
Execution trace: `c3b183ee-4ef4-4592-8638-ee275cd6c965`.
Refund trace: `fd405eb1-6743-4075-bea4-8bfad0a2723c`.
Each stage received a telemetry ingestion receipt with accepted=1, rejected=0.
The receipt organization is `68c3541d-e2d8-462a-8393-243925a5ed23`.
An accepted telemetry span is not proof of a matching policy decision in the console.
The deployed revision does not expose the enforcement receipt or matched policy ID.
Tool execution after the failed proxy request remains unconfirmed, not successful.

## Existing resources and missing relationships

| Resource | Confirmed identifier / relationship |
| --- | --- |
| Organization receiving production telemetry | `68c3541d-e2d8-462a-8393-243925a5ed23` |
| Existing MCP dashboard record supplied by owner | `2da563ef-544e-4db7-a418-0c404cf75180` |
| Public MCP service | `https://financeguard-armoriq.vercel.app/mcp` |
| SDK routing name / server name | `finance-mcp` |
| Existing Finance Agent registry ID | `0b925302-bb1d-4e44-908a-e67869e52db9`, supplied via owner's agent edit URL |
| Agent connection URL and SDK/policy linkage | Unconfirmed; supplied edit page also returns HTTP403 |
| Existing policy ID, Target Type and Target ID | Unconfirmed; no policy change proposed |
| Existing policy active flag, dates, rules and conflicts | Unconfirmed |
| Dashboard record's stored URL and organization | Unconfirmed; cannot equate the record with the public endpoint yet |

The exact supplied dashboard URL returns HTTP 403 in the available browser.
GitHub CLI and Vercel CLI have no authenticated session; deployment settings and
logs are unavailable. Public Git access does not establish write access.
The old `financeguard-demo` code default was not a verified registry identity.

The owner subsequently supplied the existing agent edit URL, confirming registry
UUID `0b925302-bb1d-4e44-908a-e67869e52db9`. This UUID is now set in ignored local
configuration and the non-secret template. It does not establish the stored
connection URL or policy relationship, and the recorded trace predates this change.

Still needed from the account holder: the agent connection URL; the MCP
record's stored service URL and organization; existing policy ID, Target Type,
Target ID, active flag, activation/expiration dates and relevant rules. Inspect
conflicting applicable policies too. Share only these non-secret fields or redacted
screenshots. Preserve MCP-targeted protection until those relationships are resolved.
Whether a separate agent-targeted policy/bundle is needed remains unconfirmed.

## MCP verification and scanning

Actual MCP initialization and tool discovery succeeded at the public service using
Streamable HTTP, protocol `2025-11-25`. Eight tools were discovered: list_invoices,
get_invoice_details, summarize_overdue_invoices, create_draft_payment_reminders,
export_sandbox_reports, simulate_refunds, transfer_funds and delete_invoices.
An unauthenticated summary returned an MCP tool error and no invoice data.
This is protocol evidence, not an ordinary REST/HTML response.

`/api/agent` is a chat REST endpoint, not an established A2A service. No A2A agent
card is implemented. The registered agent connection URL and selected framework
are unavailable, so its scan compatibility cannot be confirmed. No scan was run.
Security scanning checks the service; runtime enforcement authorizes an action;
telemetry delivers traces. These are separate operations.

## Configuration and failure causes

Production health currently reports the ArmorIQ key present, but MCP URL and MCP
signing key absent, with temporary storage. The earlier missing-key warning does
not describe the current key state. It originally came from the backend approval
path, while chat rendering separately reset the UI to Awaiting execution.

Local SDK health and bootstrap probes returned HTTP 403 with HTML rather than JSON.
The SDK constructor maps either 401 or 403 to an invalid/revoked-key exception;
that exception alone cannot establish key validity or exact HTTP status. Current
local access is blocked, while production plan creation proves the production key
works for that operation. The precise remote proxy failure needs deployment and
ArmorIQ logs; a stale registry URL is not confirmed as today's cause.

Installed and pinned SDK: `armoriq-sdk==0.6.10`. Production endpoints are explicitly
configured: backend `https://api.armoriq.ai`, proxy `https://proxy.armoriq.ai`, IAP
`https://iap.armoriq.ai`. The SDK handles API-key authentication; no client key is
substituted. Probes used the SDK's exact `/health` and `/iap/sdk/bootstrap` routes
with normal TLS verification. No endpoint guessing or authentication bypass.

| Exact variable | Host / environment | Required value |
| --- | --- | --- |
| ARMORIQ_API_KEY | Backend, Vercel Production and local ignored .env | Actual organization API credential; never the word Secret or a browser variable |
| ARMORIQ_EXPECTED_ORG_ID | Backend, same environments | `68c3541d-e2d8-462a-8393-243925a5ed23`, only if it matches the existing records |
| ARMORIQ_AGENT_ID | Backend, same environments | `0b925302-bb1d-4e44-908a-e67869e52db9`; existing registry UUID supplied by owner, SDK linkage still unverified |
| ARMORIQ_MCP_SERVER_ID | Backend, same environments | `2da563ef-544e-4db7-a418-0c404cf75180` |
| MCP_SERVER_URL | Backend, same environments | Exact existing registered service URL; public candidate verified at `https://financeguard-armoriq.vercel.app/mcp`, record match unresolved |
| FINANCEGUARD_SCOPED_MCP | Backend | `1` for workspace-scoped credential forwarding |
| FINANCEGUARD_MCP_SIGNING_KEY | Backend and MCP origin | Same private random value, 32+ characters, never committed |
| ARMORIQ_OBSERVABILITY | Backend | `true` |
| FINANCEGUARD_ALLOWED_HOSTS | MCP origin | Actual deployment hostnames, without schemes or paths |

Preview is a separate Vercel environment. Apply settings to Production for the live
app; create a new Production deployment after approved changes. Local .env changes
do not change Vercel. Secret values belong only in ignored local files or host
settings, never NEXT_PUBLIC_ or VITE_ variables.

A shared signer alone cannot share active grants or invoices. Current Vercel
SQLite /tmp and process-memory sessions are not durable shared state. An app/MCP
origin with persistent shared data and grants is required for reliable execution.
The existing local app and standalone MCP can share one persistent database;
public deployment or tunnel changes require approval. No remote hosting changed.

## Fixes prepared locally

- Exact existing MCP record ID lookup; removed unverified agent default; bootstrap
  identity/org mismatch checks. No duplicate record creation.
- Registration helper now prints a read-only proposal; it no longer upserts policies.
- Explicit enforcement HTTP receipt and optional policy ID, distinct from SDK
  intent rejection and telemetry. Incomplete policy responses fail closed.
- Sanitized config/auth/network/policy/tool errors; no invented HTTP401 when the
  SDK discards the original status, and HTML403 is not labeled a policy denial.
- UI retains actual execution outcome and shows trace/org/agent/MCP provenance.
- Missing/invalid config diagnostics and deployment revision reporting.
- Workspace credential revocation tests and reproducible real MCP/live trace tool.

These fixes are not deployed. Existing invoice-source/provider features and guide
assets are included in the pending working tree; external provider account flows
are not live-verified. No financial writes or reminders were sent.

## Reproduce and finish

Run `python tools/trace_armoriq.py --live --local-services --output docs/evidence/armoriq-trace-2026-10-17.json`
using the project's installed dependencies and ignored environment. It checks
synthetic data only and does not modify registrations or policies.

Next, resolve existing record relationships and propose any exact remote change
for approval. Then repair backend/MCP configuration and persistent shared state,
redeploy only with approval, and rerun the live trace. Inspect the intended org,
agent, time range and trace IDs in ArmorIQ. Do not claim verified=True until the
actual read-only result and SDK verification are returned. A refund denial in the
SDK alone is not proof of a cloud policy denial or dashboard decision.

Browser acceptance: open the deployed app, use sample invoices, approve only the
summary, run it, inspect a real summary and verification source, attempt the refund
under the same plan, and inspect the audit and ArmorIQ decision records. Revoke the
plan and ensure executing again fails before the tool. Repeat with two synthetic
workspaces and confirm no cross-workspace reads. Those live acceptance outcomes
remain unverified where the proxy/configuration blocks execution.

## Local verification

61 Python tests passed, including workspace isolation, missing/forged/revoked MCP
credentials, changed datasets, policy failures, SDK identity/record checks and
provider connection tests. Five JavaScript status tests passed. Python tool
compilation, JavaScript module syntax and Git whitespace checks passed. These
automated tests do not prove dashboard setup or live proxy execution. This app
uses FastAPI and plain browser modules; there is no TypeScript/Next build step.
The optional npx Prettier check produced no result and was stopped; formatting
lint is not claimed as passed.

## Official references

- [Agent registration](https://docs.armoriq.ai/platform/agents/add-agent)
- [Agent registry](https://docs.armoriq.ai/platform/agents/registry)
- [Scan reports](https://docs.armoriq.ai/platform/agents/scan-reports)
- [Observability SDK](https://docs.armoriq.ai/platform/observability/python-sdk)
- [Observability troubleshooting](https://docs.armoriq.ai/platform/observability/troubleshooting)
- [API reference](https://docs.armoriq.ai/platform/api-reference)
- [CLI registration and upsert behavior](https://docs.armoriq.ai/platform/sdk-cli/cli-reference)
