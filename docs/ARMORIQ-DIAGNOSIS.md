# ArmorIQ diagnosis — October 16, 2026

> Historical findings below are dated. See the [October 17 live integration report](ARMORIQ-INTEGRATION-2026-10-17.md) for current configuration, evidence and blockers.

## Confirmed findings

1. The public `/api/health` returns HTTP 200 but reports the ArmorIQ API key,
   MCP URL and MCP signing key absent. That deployment does not have the required
   effective configuration. Authenticated Vercel settings are not accessible in
   this execution environment (Vercel CLI reports Logged out); exact dashboard
   names, scopes, values and last
   redeployment cannot be confirmed. This does not prove the user entered a bad key.
2. Frontend requests use `/api/...` relative to the page. Vercel runs the FastAPI
   backend itself from `app.py`; no frontend API base URL needs changing.
3. The ignored local environment contains the canonical settings. Fresh real SDK
   bootstrap authenticated successfully and matched `ARMORIQ_EXPECTED_ORG_ID`.
   `finance-mcp` exists in that organization, but its registered URL differs from
   `MCP_SERVER_URL`. Discovery of the registered origin failed, yielding zero
   tools. Public discovery at the configured deployed /mcp separately returned
   eight tools, and an unauthenticated summary was denied. No registry or policy
   changes were made during this diagnosis.
4. The real synthetic workflow stopped at registration validation before plan
   execution. The local browser reproduced that error. A live ArmorIQ verified
   summary, live refund denial and new telemetry visibility remain unverified.
5. Empty chat history previously overwrote manual action status with Awaiting
   execution. The status now comes from real workspace audit events and API
   failures, independently of chat history and separately for each engine.
6. Deployed state is temporary SQLite plus process memory. Different Vercel
   instances cannot safely share invoices, grants, approvals or guest sessions.
   A shared signing key alone is insufficient. Unknown grants fail closed.

The prior missing-key message came from the backend approval path in `app.py`;
frontend `api()` displayed it. `renderConversation()` independently reset the
verification badge. Both the runtime configuration problem and UI problem existed.

## Real flow

Browser → same-origin `/api/approve` → validated backend environment → SDK
bootstrap/organization → registered `finance-mcp` URL check → SDK session plan
capture and intent token. `/api/execute` checks owner, snapshot and expiry,
then calls SDK `session.check` → SDK proxy `invoke` → registered HTTPS MCP →
signed active workspace grant → real invoice summary → SDK report/flush.

No tool runs when configuration, API authentication, policy authorization or
origin authentication fails. Out-of-plan refunds are rejected by SDK intent
binding before the proxy; that is not automatically a cloud policy-engine
decision. Global ArmorIQ token revocation has not been tested. Workspace revoke
invalidates FinanceGuard origin grants, so captured tokens cannot be replayed
against that persistent grant store after revocation.

## Configuration checklist (never include values in reports)

| Exact variable | Host and scope | Expected content |
|---|---|---|
| `ARMORIQ_API_KEY` | Actual FastAPI backend; Vercel **Production** if serving this deployment | Organization-scoped ArmorIQ API credential, not a client key or Secret label |
| `ARMORIQ_EXPECTED_ORG_ID` | Same backend, Production | Organization UUID matching authenticated bootstrap |
| `MCP_SERVER_URL` | Same backend, Production | Exact reachable public HTTPS `/mcp` URL registered as `finance-mcp` in that organization |
| `FINANCEGUARD_SCOPED_MCP` | Backend, Production | `1` to enable SDK workspace credential forwarding |
| `FINANCEGUARD_MCP_SIGNING_KEY` | Backend AND actual MCP origin; Production | Same private random key, at least 32 characters; also requires shared active grants/data |
| `ARMORIQ_AGENT_ID` | Backend, Production | Registered/demo agent identifier; default `financeguard-demo` |
| `ARMORIQ_OBSERVABILITY` | Backend, Production | `true` for real SDK session telemetry |
| `FINANCEGUARD_ALLOWED_HOSTS` | Backend AND MCP origin where needed | Exact public hostnames, comma-separated, no scheme/path or wildcard |
| `FIREBASE_PROJECT_ID` | Backend, Production | Existing Firebase Auth project; unrelated to ArmorIQ API authentication |

Use Preview separately for preview URLs; Development does not configure
Production. For a persistent backend outside Vercel, set these on that backend
instead. Local `.env` is ignored by Git and is not uploaded to Vercel.
`load_dotenv` does not override variables already provided by the runtime.
Set private values in the ignored local `.env` or the host's secure settings;
do not paste them into chat. Secret is a storage designation, not a credential.

The installed and pinned production Python SDK is `armoriq-sdk==0.6.10`
(also the latest PyPI version when checked). It handles authenticated requests;
the browser never supplies the ArmorIQ key. Its verified production services
are `https://iap.armoriq.ai`, `https://proxy.armoriq.ai`, and
`https://api.armoriq.ai`. The wrapper explicitly passes those defaults with
TLS verification on. SDK bootstrap/enforce use `X-API-Key`; its HTTP client also
manages its Authorization header. Do not invent headers or use an organization
ID as a credential. Generic `BACKEND_ENDPOINT`/`PROXY_ENDPOINT` variables can no
longer redirect this application's private credential to another service.

References: [API keys](https://docs.armoriq.ai/platform/api-keys/create-key),
[SDK quickstart](https://docs.armoriq.ai/platform/sdk-cli/quickstart),
[Observability](https://docs.armoriq.ai/platform/observability/python-sdk),
[MCP registration](https://docs.armoriq.ai/platform/mcp-servers/add-server),
[Vercel environment changes](https://vercel.com/docs/environment-variables).

## Changes awaiting deployment approval

Sanitized structured errors distinguish configuration, authentication, policy,
token, network, provider and tool failures. Malformed or unavailable enforcement
responses stop execution and are not relabeled as a policy decision. Upstream
SDK log bodies are withheld. Health/state expose variable statuses, never values.
MCP grants enforce origin revocation and reject unknown grants. SQLite
connections close deterministically. UI evidence no longer depends on chat history.

Before any deployment, choose a persistent app/MCP host or implement shared
durable state. Review exact settings on the actual backend. Approve updating
the `finance-mcp` registration to that reachable origin in the matching org.
If registration still returns 500, preserve the failure and resolve it with
ArmorIQ support; do not disable policy or substitute successful mock output.

After approval, deploy reviewed code and correct settings as a NEW Production
deployment, then repeat real SDK checks. A redeployment alone will not fix
the unreachable registry or the distributed state problem.

## Validation performed

- 45 Python automated tests passed, including actual ASGI MCP calls, imported
  totals, identity and workspace isolation, wrong scope, expiry, grant revocation,
  denial, malformed enforcement and authentication failures. SDK cloud HTTP
  is mocked in those unit tests and is not evidence of a live provider pass.
- Five Node status regression tests passed; JavaScript syntax and changed Python
  compilation passed. This plain Python/JavaScript app has no TypeScript or
  Next.js build/type-check pipeline; no such build is claimed.
- Local browser: real ArmorIQ registration failure stayed visible; a local MCP
  summary executed with `verified=False`; refund simulation blocked; revocation
  disabled Run. Existing Firebase test session was reused, not a new sign-up test.
- Real local-key SDK bootstrap passed. Registry health failed. Real safe workflow
  stopped before execution. No real payments or invoice writes were performed.
- Production private settings, new deployment, live verified execution, live
  provider denial/revocation and console trace visibility remain unverified.

## Browser checklist after approved deployment

1. Open `/api/health`: correct revision/environment, no missing/invalid settings;
   remember configured does not mean verified.
2. Sign in; import only a synthetic INR CSV; check its count and total.
3. Select ArmorIQ, approve summary, run. Require actual matching totals and
   `verified=True`; an error must stay an error through refresh/history loading.
4. Attempt refund under the same plan. Require BLOCKED, unchanged invoices and
   an accurately labeled SDK/provider denial in Activity.
5. Revoke; confirm Run is disabled and previous origin credentials are denied.
6. Check a second workspace cannot read the first. Check a changed CSV requires
   new approval. Check Activity and ArmorIQ console separately for real receipts.
