# FinanceGuard

Created by **Anuj A Shetty and Yuvraj Singh**. [Creators](AUTHORS.md).

**Approved actions execute. Unauthorized actions get blocked.**

FinanceGuard is an MCP finance operations assistant for small businesses and
accountants. It reviews invoices, prepares reminder drafts, and exports reports
under an explicitly approved plan. It never moves money or sends emails.

## Problem

Giving an agent valid credentials does not mean every action it tries is
approved. An invoice review must not silently become a refund or transfer.

## Solution

The user chooses a source, selects one action, and approves a five-minute plan.
In ArmorIQ mode, the backend creates an SDK session, captures the plan, obtains
an intent token, checks permission, invokes the MCP through ArmorIQ, reports the
actual execution, and flushes observability. A refund outside that scope is
rejected by SDK intent binding before the proxy invocation.

The request panel uses deterministic command routing. No general LLM, voice,
payment gateway, bank account, or customer payment-provider OAuth is connected.

The workspace opens directly to the invoice inventory: search by customer or
invoice, filter statuses, sort, inspect details, and export CSV. Sign in to
import an accounting/spreadsheet CSV, or link a local CSV file and explicitly
refresh its snapshot. Each import is previewed and clears old approvals.
See [invoice sources and limitations](docs/INVOICE-SOURCES.md). File linking
does not connect a private Google Sheets or accounting-provider account.

## Demo

- Useful action: `summarize_overdue_invoices`.
- Sample result: three overdue invoices totaling INR 88,000, calculated from
  [the repository dataset](data/invoices.json).
- Boundary test: `simulate_refunds` under the summary plan.
- A real SDK result can report `verified=True`; this is the SDK invocation
  status, not an independently signed receipt or proof of a cloud audit row.
- Local policy mode remains available and is explicitly labeled unverified.

[Live demo](https://financeguard-armoriq.vercel.app) ·
[Recording runbook](docs/DEMO-RECORDING.md) ·
[Submission pack](docs/SUBMISSION.md) ·
[Observability setup](docs/OBSERVABILITY.md)

## Current verification status

Update: the newly saved key now authenticates to the intended Yuvaraj workspace.
The ngrok registration was unreachable. The deployed MCP host/signing fix and
private Vercel import helper are documented in [Vercel setup](docs/VERCEL.md).
A fresh real-provider invocation and trace check remain required after the
private hosting variables are imported.

### Earlier verification

Earlier local real-provider execution evidence is preserved in
[docs/evidence](docs/evidence/API-VERIFICATION.md). Those October 15 results
belong to Anuj's organization and predate the session instrumentation.

The October 16 session implementation is tested with the installed production
SDK and mocked provider HTTP. Those tests are not live ArmorIQ evidence.
That earlier organization mismatch was resolved by the current key. Registration
now fails with HTTP 500 through both SDK and console, despite successful public
discovery. See [current connection evidence](docs/MCP-CONNECTION-STATUS.md).
New live trace ingestion and console visibility must pass before recording
or claiming a finished ArmorIQ demo. No traces or successful results are seeded.

## Tech stack

Python 3.12/3.13, FastAPI, ArmorIQ SDK 0.6.10, MCP Streamable HTTP, Firebase
Authentication, owner-scoped SQLite, and a dependency-free HTML/CSS/JS frontend.
The SDK is pinned for reproducibility; session tracing exists in this version.

## Local setup

```powershell
git clone https://github.com/Yuzy67/financeguard-armoriq.git
cd financeguard-armoriq
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# New checkout only: never overwrite an existing private configuration.
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001. No ArmorIQ key is needed for the sample/local mode.
Use Firebase sign-in to preview/import a CSV. In Security, select local mode,
approve the summary, run it, then attempt a refund and inspect Audit Log.

For the real ArmorIQ path:

1. Privately configure a replacement `ARMORIQ_API_KEY` for the intended org.
2. Set `ARMORIQ_EXPECTED_ORG_ID`, `ARMORIQ_AGENT_ID`, and `MCP_SERVER_URL`.
3. Start the standalone workspace MCP using `start-mcp.ps1` on port 8002.
4. Expose only that MCP via a public HTTPS origin/tunnel. Keep the process up.
5. Register/update the exact URL in the same organization:
   `.venv\Scripts\python.exe tools/register_mcp.py https://YOUR-HOST/mcp`.
6. For this workspace-scoped origin set `FINANCEGUARD_SCOPED_MCP=1`. The app and
   standalone MCP must share the same local runtime/database/signing key.
7. Run `.venv\Scripts\python.exe tools/check_setup.py` and resolve any drift.
8. Run `.venv\Scripts\python.exe run_financeguard_demo.py`.
9. Check the printed session UUID in the correct ArmorIQ Observability view.

`MCP_SERVER_URL` is checked against ArmorIQ's registry; it does not override the
proxy with an arbitrary browser-supplied endpoint. Do not disable TLS validation.

## Security model

Firebase tokens are checked server-side for signature, project, issuer, expiry,
and identity. Imports and activity are isolated by verified UID. MCP credentials
bind owner, action, dataset fingerprint, and expiry. Missing/forged credentials
and changed data fail closed. Each draft/report needs its own explicit approval.

The key stays in backend environment variables. `.env`, `armoriq.yaml`, runtime
signing keys, database files, and credentials must never be committed.
A key was exposed in earlier upstream Git history; it must be revoked. Removing
it from the current template does not erase that history. Do not force-push a
shared-history rewrite without coordinating with both maintainers.

## API

Existing `/api/approve` and `/api/execute` routes remain supported.

- `POST /api/run-approved-action`: execute the already approved summary.
- `POST /api/attempt-refund`: attempt refund under that same plan.
- `GET /api/audit-log`: owner-scoped application action trail with SDK IDs and
  ingestion receipts where present; not a substitute for cloud console access.
- `GET /api/health`: non-sensitive runtime status.

POST action bodies accept `{"engine":"local"}` or `{"engine":"armoriq"}`.
Execution never grants an implicit approval. Authentication is required; the
sample session is established by `POST /api/demo` with an HTTP-only cookie.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Tests cover identity forgery, owner isolation, CSV validation, plan expiry and
revocation, denied mutations, drafts/reports, actual ASGI MCP calls on a
simulated Vercel cold start, API aliases, and SDK trace/report/delivery behavior
using mocked provider HTTP. Tests never claim external console visibility.

## Vercel and limitations

See [Vercel deployment](docs/VERCEL.md). The source is read-only on Vercel; the
hosted demo uses temporary storage and displays that limit. Data and approvals
may reset or differ across instances. Durable multi-instance hosting needs a
shared store; Firebase web configuration alone does not provide one.

A locally registered MCP reads local data. It cannot automatically read a
separate Vercel instance's uploaded invoices. For judging, use the stable sample
dataset on both sides, or run the entire scoped workflow on the same persistent
backend. Do not claim cloud-upload parity until shared storage is verified.

## Hackathon

Built for Flow State by ArmorIQ. #FlowStateHackathon

The official event page lists submissions closing October 17 and uses UTC,
without an exact hour. Confirm the final form's timezone and deadline; the
teammate-provided 11:59 PM IST must not be assumed from the public page.
