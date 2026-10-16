# FinanceGuard: five-hour delivery plan

This is a plan, not evidence that the proposed integrations already work.

## Scope

Deliver one complete workflow: Firebase sign-in -> CSV workspace -> user-approved
summary plan -> OpenRouter tool proposal -> ArmorIQ enforcement -> actual MCP
summary -> explanation -> refund denial under the same plan -> audit -> drafts.
Razorpay test-mode invoice sync is optional. Defer PhonePe, live payments,
customer gateway OAuth, and a frontend framework rewrite.

## 0-60 minutes: ArmorIQ and deployment

The current local key authenticates in the intended organization. Keep it.
The deployed MCP URL is https://financeguard-armoriq.vercel.app/mcp; discovery
returns eight tools. Both SDK and console registration return HTTP 500.

Import ignored runtime/vercel-production.env into Vercel Production and redeploy.
Recheck configuration, public discovery, and denial of missing credentials.
Timebox registration reproduction to 20 minutes. Prepare sanitized timestamps,
SDK version, organization, URL, HTTP status and any request ID for the organizer;
do not include keys or tokens. The existing support-note draft has not been sent.

If registration remains broken, test the documented SDK-mode lifecycle:
start_plan -> check -> execute the actual MCP tool only on allow -> report ->
flush. Determine experimentally whether plan capture/enforcement works without
the failed registry operation. This route is a candidate, not a proven bypass
of the registration dependency. Do not skip enforcement, disable TLS, or turn
provider errors into permission. If it fails, retain a clearly labeled local
demo and report the ArmorIQ blocker; do not claim a verified ArmorIQ demo.

Evidence must distinguish an SDK permission decision, actual MCP completion,
proxy invocation verified=True, telemetry acceptance, and console visibility.

## 60-150 minutes: OpenRouter brain

Use a backend-only OPENROUTER_API_KEY and configurable, tool-capable model.
Validate tool names and arguments server-side. Bound calls, output tokens and
runtime; execute tools sequentially. The model proposes actions; the human
approves scope. A model request cannot approve or expand its own plan.
Every agent tool request passes ArmorIQ before execution, including reads,
drafts, exports and any gateway sync. Keep workspace credentials server-owned.
Treat invoice text as untrusted data, not instructions. Send only the invoice
fields needed for the requested task to the model. Record usage without secrets.
On denial, error or expiry, do not execute the tool or invent a successful result.

## 150-180 minutes: optional Razorpay test sync

Proceed only if the core is working and test credentials are already ready.
Implement an operator-only, read-only invoice adapter using documented invoice
GET APIs. Keep test key ID and secret in backend environment settings. Normalize
currency and minor units, outstanding amounts, pagination and available dates.
Do not infer missing due dates. Clearly label test data and source.
Import into the signed-in workspace; changed data invalidates existing approvals.
Require fresh approval before analysis. No payment collection or message sending.
If account setup or adapter verification exceeds this timebox, use CSV.

## 180-240 minutes: end-to-end proof

Test actual browser signup/sign-in/sign-out, CSV import and persistence at the
chosen demo origin. Test two users, forged/missing workspace credentials,
changed data, expiry, refunds, draft-only reminders, reports and provider outage.
Verify model tool requests traverse enforcement and cannot call tools directly.
Capture actual request/event correlation and inspect the correct ArmorIQ console.
Vercel temporary storage is not durable shared storage: do not claim durable
cloud CSV workspaces until implemented and verified. Choose a stable demo origin
with durable workspace storage or explicitly disclose the preview limitation.

## 240-300 minutes: freeze and submit

Stop adding features. Record the actual 3-5 minute flow, showing approved scope,
real result, unauthorized refund denial and real audit evidence. Use the existing
DEMO-RECORDING.md runbook and sample workflow backup. Verify README launch steps,
secret-free template, source link and live origin. Never fabricate provider proof.

## Human setup only

Import the prepared private Vercel environment file and redeploy. Add an
OpenRouter key privately to ignored .env and deployment settings. Optionally
provide Razorpay test credentials in those same private locations. Contact the
organizer with the sanitized registration note if HTTP 500 persists. Never
paste private credentials into chat or commit them.

## Official references

- https://docs.armoriq.ai/platform/observability/python-sdk
- https://openrouter.ai/docs/guides/features/tool-calling
- https://razorpay.com/docs/api/payments/invoices/
- https://razorpay.com/docs/payments/dashboard/test-live-modes/
