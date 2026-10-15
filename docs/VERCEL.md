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
