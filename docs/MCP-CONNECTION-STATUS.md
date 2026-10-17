# FinanceGuard MCP connection status - 16 October 2026

> Historical findings below are dated. See the [October 17 live integration report](ARMORIQ-INTEGRATION-2026-10-17.md) for current configuration, evidence and blockers.

## Verified

The current private key passes the SDK health check (HTTP 200) and authenticated
bootstrap (HTTP 200), resolving to Yuvraj Singh's Workspace, organization
68c3541d-e2d8-462a-8393-243925a5ed23. The effective key matches the local file;
there is no stale process-level key overriding it in the diagnostic run.
The earlier rejection is no longer reproducible; its original cause is unknown.

The registered ngrok origin is unreachable. Our deployed endpoint is now:
https://financeguard-armoriq.vercel.app/mcp

After the exact-host fix, real discovery succeeds and returns all eight tools.
An unauthenticated summarize_overdue_invoices request returns an MCP tool error.
Host/Origin validation remains enabled. No real invoice contents were fetched
by the unauthenticated connectivity tests. All 24 automated tests pass locally.

## Remaining blockers

1. Vercel /api/health currently reports armoriq_configured=false,
   mcp_signing_configured=false, and mcp_url_configured=false. Import the private
   runtime/vercel-production.env file into Production environment variables and
   redeploy. The file is Git-ignored; never share or commit it.
2. SDK registration POST /iap/sdk/register returns HTTP 500. The actual ArmorIQ
   console registration flow, in the correct workspace, also returns Internal
   server error when registering finance-mcp at the deployed URL. Public MCP
   discovery succeeds before registration. This is not proof that the API key
   is invalid and is not an application-side fabricated success.

## Provider support note (draft only; not sent)

FinanceGuard key authentication and bootstrap both return HTTP 200 for org
68c3541d-e2d8-462a-8393-243925a5ed23. We are registering finance-mcp at
https://financeguard-armoriq.vercel.app/mcp. SDK MCP discovery finds eight tools.
The installed armoriq-sdk 0.6.10 CLI registration endpoint returns HTTP 500.
The console's Connect by URL / Register server flow returns Internal server
error for the same public endpoint in Yuvraj Singh's Workspace. Please inspect
the registration error for this organization. No API key or intent token is
included in this report. We have not disabled TLS or host validation.

## Invoice tools

The server implements invoice listing, invoice details, overdue summary,
reminder drafts, and report export. Refund, transfer, and deletion tools remain
disabled simulations. Sources are CSV imports or sample data, with no payment
gateway or bank connection required. A shared signing key alone does not share active grants or invoice data. Unknown
grants fail closed, including for sample data. Durable shared storage is required
before claiming multi-instance execution works.
