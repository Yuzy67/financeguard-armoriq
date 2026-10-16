# Vercel deployment

Production URL: https://financeguard-armoriq.vercel.app

Vercel detects app.py as the FastAPI entrypoint. vercel.json sets a 60-second
function timeout. The frontend and sample invoices ship with the application.

## Runtime compatibility

- VERCEL=1 selects the writable temporary directory, never the read-only source.
- Trusted hosts include the exact VERCEL_URL, VERCEL_BRANCH_URL, and
  VERCEL_PROJECT_PRODUCTION_URL supplied by Vercel. Add exact custom domains
  through FINANCEGUARD_ALLOWED_HOSTS; do not use a wildcard.
- Guest cookies are Secure on Vercel.
- Local-mode MCP uses a fresh ASGI server and the real initialize/tools/call
  protocol within the function. No localhost TCP listener is required.
- GET /api/health exposes non-sensitive runtime/configuration status.

## Environment configuration

For AI chat, set OPENROUTER_API_KEY and OPENROUTER_MODEL on the backend only.
The private runtime/vercel-production.env preparation helper includes these
when present locally. New environment values require a redeploy. A free model
may be rate-limited; a configured key does not prove a successful model call.
Conversation history uses the same temporary SQLite storage limitation below.

Set private ARMORIQ_API_KEY in Vercel project settings only. Use a replacement
for the key previously exposed in Git history. Set FIREBASE_PROJECT_ID=asmoneykit.
Add financeguard-armoriq.vercel.app to Firebase Auth authorized domains if needed.
Keep FINANCEGUARD_SCOPED_MCP=0 until the registered external MCP origin can access
shared persistent data with a consistent signing key. The temporary tunnel used
for earlier local testing is stopped and is not the deployed MCP service.

## Current storage limit

This deployment is a temporary hosted demo. SQLite, guest sessions, approvals,
and local activity can reset on cold starts or differ across instances. A notice
in the UI states this. Uploaded CSV files are not durably stored by Vercel.
Approvals fail closed when absent; data changes invalidate an existing approval.

For persistent hosted use, connect a shared database and move approvals, guest
sessions, and workspace credentials to a consistent shared store. The Firebase
web configuration only provides Auth setup; it does not grant server database
access. Do not present this deployment as durable production storage.

## Verify after deployment

Check /, /assets/app.js, /assets/style.css, /favicon.ico, and /api/health. Start a
sample workspace, approve a summary, run it, attempt a refund, inspect the trail.
The Vercel regression test runs the real MCP protocol without a network listener.

## Session tracing update

The web API now uses ArmorIQWorkflow session instrumentation. Configure the
expected organization, agent, current MCP_SERVER_URL, and observability flag as
shown in .env.example. A wrong organization or stale registration refuses plan
creation. Application audit rows expose real SDK IDs and per-flush delivery
receipts, never intent tokens. See OBSERVABILITY.md.

Do not forward a Vercel-generated scope credential to a separate local database
and expect user-upload parity. Use sample data in both runtimes, or host the
app and origin together with durable shared state before claiming imported
cloud invoices work through that remote origin.

## Stable deployed MCP endpoint (current setup)

The intended endpoint is https://financeguard-armoriq.vercel.app/mcp.
The MCP transport now accepts exact configured deployment hosts with DNS
rebinding protection still enabled. Missing scope credentials still deny
invoice tool access; discovery only lists tool names and schemas.

For a stable hosted sample demonstration, set a private
FINANCEGUARD_MCP_SIGNING_KEY (32+ random characters) consistently across
instances and FINANCEGUARD_SCOPED_MCP=1. The built-in sample dataset is the same
on every instance, so a sample scope can be verified across separate instances.
This does not make uploaded data or plans durable across server restarts.

Run tools/prepare_vercel_env.py locally to validate your current key and create
runtime/vercel-production.env. It is a private Git-ignored import file, not a
submission artifact. It includes the current API key, expected organization,
public MCP URL, and matching signing key. Never paste or commit its contents.

Import that file in Vercel project Settings / Environment Variables for
Production, save, and redeploy. After deployment, /api/health must show both
armoriq_configured=true and mcp_signing_configured=true. Those booleans only
confirm settings exist; a real SDK invocation must still verify they work.

Register the deployed HTTPS /mcp URL in ArmorIQ's matching organization using
tools/register_mcp.py, then run tools/check_setup.py and the real demo. No laptop
tunnel is needed for this endpoint. Do not expose /runtime or configuration files.
