# Vercel deployment

Production: https://financeguard-armoriq.vercel.app

Vercel runs app.py as FastAPI, serving both the frontend and /api routes.
api.py is a compatibility alias. Frontend fetches are same-origin, not a
separately hosted API. vercel.json sets a 60-second function timeout.

See [current diagnosis and exact configuration](ARMORIQ-INTEGRATION-2026-10-17.md).
Changes to remote configuration, registration or deployment require approval.

## Runtime compatibility

- VERCEL=1 selects writable temporary storage. It is not a persistent database.
- TrustedHostMiddleware and MCP DNS rebinding protection accept exact deployment
  hosts supplied by Vercel; custom domains use FINANCEGUARD_ALLOWED_HOSTS.
- Guest cookies are Secure. Cross-origin writes are rejected.
- Local policy mode uses actual MCP initialize/tools/call over ASGI within the
  function; it does not require a localhost listener.
- ArmorIQ mode invokes the external registered MCP through the real SDK proxy.
- /api/health exposes sanitized configuration checks and deployment metadata.
  Configuration present does not imply authentication, execution or verification.

## Persistent state is required for reliable hosted execution

SQLite files under /tmp, guest sessions and SDK approval objects in process
memory can disappear or differ between invocations. Public /mcp requests may
reach a different instance than the one issuing an approval. Importing keys
and redeploying alone does not solve this architecture limitation.

Origin tokens now include an approval grant ID. The MCP checks signature,
owner, action, dataset fingerprint, expiry and the active grant before reading
invoices. Revocation marks origin grants invalid. Unknown grants fail closed.
A shared signing key does not supply missing grants, even for sample invoices.

For the fastest dependable demo, run this app and its /mcp endpoint together
on one persistent backend and register that backend's public HTTPS /mcp URL.
Local same-process testing on port 8004 is verified, but external hosting and
registration still require approval and validation. Alternatively implement
shared durable invoices, grants/revocations, approvals and identity sessions
before using distributed serverless instances. Firebase web configuration only
sets up Auth; it does not provide server database authorization.

## Environment updates

Use exact names from .env.example in the actual backend host. Select Production
for the public production domain; use Preview separately for preview deploys.
A Secret designation is appropriate for private credentials. The value must be
the credential, not the word Secret. Never use NEXT_PUBLIC_ or VITE_ prefixes.
Save settings and create a NEW deployment; existing deployments retain their
old environment. Do not commit .env, armoriq.yaml or runtime import files.

FINANCEGUARD_SCOPED_MCP=1 and the shared private signing key are required for
ArmorIQ workspace access. The matching origin must also have the same approved
grants and invoice snapshot, not only the signing key.

The existing tools/prepare_vercel_env.py produces a private ignored import file;
it does not deploy, register an origin or solve shared storage. Do not upload
or apply it without reviewing the intended Production target and approval.
