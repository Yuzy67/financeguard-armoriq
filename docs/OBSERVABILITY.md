# ArmorIQ observability: implementation and verification

> Historical findings below are dated. See the [October 17 live integration report](ARMORIQ-INTEGRATION-2026-10-17.md) for current configuration, evidence and blockers.

## Root cause

The old script called capture_plan/get_intent_token/invoke directly. It did not
create ArmorIQSession, run its check/report lifecycle, or close/flush a session.
The installed SDK's recorder is session-owned; raw invocation success does not
prove trace creation or delivery.

Official reference: https://docs.armoriq.ai/platform/observability/python-sdk

## Implemented

armoriq_workflow.py uses the installed armoriq-sdk 0.6.10 session API:

1. Bootstrap identity and reject an unexpected organization.
2. Verify finance-mcp registration and configured URL equality.
3. Start an SDK-mode session with a valid UUID and explicit observability.
4. start_plan captures the single approved action and mints its token.
5. check records the actual allow/deny result. Provider errors stop execution.
6. invoke runs the approved MCP through the original SDK proxy flow.
7. report records the real execution outcome, withholding invoice content.
8. flush_observability ends the trace and ships synchronously.
9. close stops the background shipper before closing its HTTP client.

An HTTP response hook stores only ingest status and accepted/rejected counts.
No request headers, tokens, API keys, or arbitrary response bodies are persisted.
Telemetry failure does not authorize execution or fabricate a delivered trace.

The CLI puts the plan, safe check, tool report, and refund check in one trace.
The web app flushes at each HTTP action boundary for serverless delivery: traces
are separate but retain the same SDK session UUID under the approved plan.
The audit UI shows real SDK-generated IDs separately from local event UUIDs.

## What a refund denial means

The session's SDK checker rejects a tool absent from its plan before contacting
the enforce endpoint. The original invoke call then raises its actual
IntentMismatchException before contacting the proxy. Observability can carry
that SDK-sourced denial to the cloud. It is not a proxy policy-engine decision.

An accepted ingest response means the provider accepted telemetry. It does not
independently prove the correct user can view the row in the console. Neither
does SDK verified=True prove a signed receipt or a dashboard decision count.

## Environment

Set ARMORIQ_API_KEY privately, plus ARMORIQ_EXPECTED_ORG_ID,
ARMORIQ_AGENT_ID, MCP_SERVER_URL, and ARMORIQ_OBSERVABILITY=true.
ARMORIQ_EXPECTED_ORG_ID is required explicitly and must match authenticated bootstrap.
Workspace credential forwarding and the private signing key are also required.
The SDK uses its documented backend and appends its own spans endpoint. Do not
invent tracing endpoints or append /observability/spans to a base URL variable.

## Current external blocker (October 16)

The latest local key passes authenticated bootstrap for the target organization
68c3541d-e2d8-462a-8393-243925a5ed23. Public discovery at
https://financeguard-armoriq.vercel.app/mcp returns eight tools, and invoice
access without a credential is denied. Registration of that URL still returns
HTTP 500 through both the installed SDK and the actual console. The registry
still references an unreachable ngrok origin. Vercel also needs its prepared
private Production environment settings imported and a redeploy. New live
ingestion and console visibility are not yet confirmed. See
MCP-CONNECTION-STATUS.md for the latest evidence and a support-note draft.

## Prove delivery and visibility

1. Keep the currently authenticated target-organization key locally; install
   the private Production environment settings in Vercel and redeploy.
2. Keep the actual MCP origin reachable and update its registration/URL.
3. Run tools/check_setup.py; all identity/registry/discovery checks must pass.
4. Run run_financeguard_demo.py. Require actual safe success and SDK denial.
5. Inspect the printed ingest accepted/rejected counts. No 2xx acceptance means
   there is no confirmed delivery, even if the tool invocation succeeded.
6. Select the exact organization, agent, current date range, and SDK session
   UUID in Observability. Inspect plan, allow/deny policy spans and tool activity.
7. Capture that actual console view. Do not recreate it in an animation.
8. A dashboard Decisions chart, Policy Studio rules, and Observability traces
   are different surfaces; do not treat one as proof of another.

If rejected: inspect HTTP status, org/key access, SDK version, valid UUIDs, and
shutdown/flush timing using the official troubleshooting guide. Do not weaken
TLS or copy tokens to the frontend to work around an error.
