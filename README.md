# FinanceGuard

A finance operations workspace with explicit action plans, invoice imports,
Firebase sign-in, and visible execution decisions.

**Approved actions execute. Unauthorized actions get blocked.**

## Run

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only for new checkouts without .env:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001. Preserve an existing .env instead of overwriting it.
The start.ps1 helper installs dependencies and starts the current app.
Neither .env nor armoriq.yaml should ever be committed.

## What works

- Responsive dark dashboard with source setup, invoice filters, approval
  controls, request panel, downloads, and owner-scoped activity.
- Local sample demo: three overdue invoices totaling INR 88,000.
- Five-minute plans for invoice lists, summaries, reminder drafts, and reports.
- Explicit revocation and denial of actions outside the approved plan.
- Firebase sign-up/sign-in/reset UI and backend ID-token verification.
- Authenticated CSV preview/import; SQLite records isolated by verified UID.
- Test-only Stripe invoice adapter, restricted to one verified operator email.
- Server-side ArmorIQ plan capture and protected invocation integration.
- Repaired FastMCP origin exposing the original eight sandbox tools on 8002.
- Integrated /mcp endpoint on 8001: local invoice actions now use actual MCP
  calls with owner/action/data/expiry-scoped server-side authorization.

Local and ArmorIQ execution modes are visibly distinct. A cloud verified badge
requires SDK verified=True. Failed cloud calls do not fall back to fake success.

## External status

Update, 15 October 2026: actual browser testing passed Firebase sign-up,
sign-out/sign-in, CSV persistence, and real ArmorIQ execution against the
imported workspace with SDK verified=True. Refund under that same plan raised
IntentMismatchException in SDK validation. Draft and report tools also executed.
Verification evidence is committed in docs/evidence/, with the animated
explainer and scene preview in docs/demo/. A temporary tunnel enabled the external test and
is stopped afterward; register a fresh public origin URL to repeat it.

The earlier Internal Proxy Error was resolved by registering the current MCP
origin and using the installed SDK's documented production proxy. Local
workflow remains independent of external tunnel availability. Stripe is not
part of the current UI or demonstrated workflow.

The request panel routes supported commands deterministically. It is not a
connected general LLM or voice assistant. Customer payment-provider OAuth,
live payments, bank/card access, and public deployment are not implemented.

## Detailed setup and demo

Read docs/READY-TO-TEST.md for connection steps, limits, and judging flow.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Tests cover approval/expiry/revocation, CSV validation, workspace isolation,
mutation denials, drafts/reports, Stripe conversion with mocked responses,
and forged/expired/wrong-project Firebase token rejection.

## Data and credentials

Firebase Auth establishes identity; it does not fetch invoices. The app uses
local SQLite instead of Firestore for this single-server demo. Runtime data,
private provider keys, and tokens are never served as static assets.

Keep runtime/ durable for local data. Plans and demo sessions reset on restart.
This is a local judging build, not a production financial service. Production
hosting needs durable storage, rate limits, token revocation checks, TLS,
and a supported provider onboarding flow.
