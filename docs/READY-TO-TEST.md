# FinanceGuard: current build

## Verified update — 15 October 2026

Real browser testing now passed Firebase account creation, sign-out/sign-in,
CSV import persistence, summary execution, reminder drafts, report download,
and activity export. A new temporary HTTPS MCP registration plus supported
SDK bearer forwarding made ArmorIQ execution succeed on the imported data:
SDK verified=True, three overdue invoices, INR 88,000. Refund under the same
plan raised IntentMismatchException in SDK validation before proxy execution.

The previous proxy failure described below is historical. The SDK's production
default proxy works; the legacy proxy suggested in the registration response
did not accept this key. Use FINANCEGUARD_SCOPED_MCP=1 only with our registered
scope-checking origin. The temporary tunnel is stopped after testing, so a
fresh public URL must be registered before another external demonstration.
See ../../financeguard-evidence/TEST-RESULTS.md and the actual captures.

Start with `powershell -ExecutionPolicy Bypass -File .\start.ps1` in this project.
Open http://127.0.0.1:8001. The older AsmoneyKit app at port 8000 is separate.
The maintained application entrypoint is `app:app`; `api.py` is a compatibility
import of the same application.

Update: local actions now make real Streamable HTTP MCP calls through the
integrated http://127.0.0.1:8001/mcp endpoint. No second server is required.
The backend issues a five-minute signed MCP credential scoped to the owner,
permitted action, and invoice fingerprint. MCP invoice calls require it.
The signing key lives in ignored runtime/mcp-signing.key, never in browser
code. Tool discovery itself reveals no invoice data. Calls without a valid
workspace credential return a tool error. This does not complete the remote
ArmorIQ registration or credential-forwarding setup.

## Test without any new accounts

1. The app starts an isolated sample session using an HttpOnly cookie.
2. Keep execution mode **Local workspace**.
3. Approve **Summarize overdue invoices**, then click **Run approved action**.
4. See three overdue sample invoices totaling INR 88,000.
5. Attempt a refund, transfer, and deletion. All are blocked by the local plan.
6. Approve **Prepare reminder drafts**, then run it. Inspect/download drafts.
7. Approve **Export invoice report**, run it, and download the JSON report.
8. Inspect activity; each event identifies its execution engine.

## Use your own invoices

1. Open Account and create/sign into a Firebase account.
2. If Firebase reports operation-not-allowed/configuration-not-found, enable
   Email/Password in the project's Firebase Authentication console.
3. Download the CSV template, fill it in, and choose the file.
4. Review the preview and confirm replacement of your workspace dataset.
5. Approve a new local plan. The old plan is invalidated by a data change.

Firebase ID tokens are verified server-side for signature, issuer, audience,
expiry, and identity. Data is stored locally in SQLite under the verified UID.
Firebase Auth works without a Firebase Admin service-account key; Google
publishes the signing certificates. This build does not use Firestore.
Manual sign-up/sign-in passed with a synthetic test user in the browser.

Demo sessions cannot import private invoices or use the operator Stripe
connector. Invalid bearer tokens are rejected rather than falling back to a
demo identity. Signing out hides the authenticated user's data and returns
to a separate sample workspace.

## Optional Stripe sandbox connection

Add these to the ignored backend .env and restart:

```dotenv
STRIPE_SECRET_KEY=your_test_mode_key
STRIPE_OPERATOR_EMAIL=your_verified_firebase_email
```

Use only sandbox/test keys. The operator must verify their Firebase email.
Click **Sync test invoices** after sign-in. The adapter performs only GET
invoice reads, handles pagination, converts minor units to INR, and refuses
live data, non-INR currency, missing due dates, and invalid invoice records.
All rows validate before the workspace is replaced. Positive amounts only.
There are no real charges, Checkout, refunds, or payment transfers.

This is an operator-only sandbox integration, not customer OAuth onboarding.
An arbitrary user must not receive access to the operator's Stripe data.
Customer OAuth requires a separate provider application and implementation.
No Stripe key is currently supplied, so this adapter has been tested with
controlled provider responses, not a live sandbox. Sample/CSV works now.

## ArmorIQ demonstration

Choose **ArmorIQ** mode while using sample invoices. Approve summary, run
the safe action, then attempt refund with the same approved token.
Tokens and SDK clients are stored server-side per workspace.

Prior genuine tests: plan capture/token issuance succeeded, refund raised
IntentMismatchException, safe execution returned Internal Proxy Error. A
registry lookup with the current key returned no MCP servers. The source of
the proxy failure is not proven; account registration/health must be checked.
These are previous diagnostic results, not prefilled dashboard events.

The SDK may reject an out-of-plan request before contacting the proxy.
We report an SDK intent rejection truthfully; this is not automatically a
cloud audit event. Only an actual SDK verified=True result enables the badge.

Imported workspaces can use ArmorIQ when FINANCEGUARD_SCOPED_MCP=1 and our
registered origin is active. Per-call credentials restrict the owner, tool,
data snapshot, and lifetime. With that setting off, imports remain restricted
to local execution to avoid analyzing the wrong remote dataset.

## Running our own MCP origin

The integrated origin uses the installed FastMCP SDK and Streamable HTTP.
The following standalone command is optional for separate-origin deployment.
Run `.\.venv\Scripts\python.exe finance_mcp/server.py` on port 8002.
Its endpoint is http://127.0.0.1:8002/mcp. It exposes eight sandbox tools.
For ArmorIQ access, configure your ngrok account and run
`ngrok http 8002 --host-header=rewrite`, then register its current HTTPS /mcp
URL in the correct ArmorIQ organization as finance-mcp. Invoice tools now
require the scoped bearer credential from the backend; registering the URL
alone is insufficient. Supported SDK MCP credential forwarding must be
configured/tested before the remote path can read a workspace. None of these
tools moves money. Tool execution through the protected path must be retested.

## Scope and deployment limits

The request panel is a command-based tool workflow, not a general language
model or voice agent. It supports summaries, invoice lists, drafts, exports,
and boundary tests. It never treats a chat request as approval.

Workspace invoices and events persist in runtime/workspace.sqlite3. Plans and
guest session cookies expire or reset on server restart. Activity export is
JSON. SQLite is suitable for this single-server demo; do not run multiple
workers with independent in-memory plans or use ephemeral serverless disks.
Firebase checks do not currently check token revocation, and the app has no
production rate limiting. Run locally for judging; public hosting requires
those controls, TLS, durable storage, appropriate data retention, and correct
allowed-host/HTTPS configuration. There is no Supabase dependency.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Tests exercise unauthenticated/forged-token denial, same-origin requests,
workspace isolation, atomic CSV preview/import, plan invalidation/expiry,
local denial of mutations, draft/report results, and mocked Stripe conversion.
They do not claim verified provider OAuth, manual Firebase login, voice,
public deployment, or successful ArmorIQ safe invocation.
