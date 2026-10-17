# Invoice sources and provider setup

FinanceGuard now presents three entry choices after sign-in: sample invoices,
CSV import, or provider connection. The provider picker includes Zoho Invoice,
Razorpay Test Mode and Stripe restricted test keys. Each uses an explicit
preview followed by confirmation that replaces the current workspace snapshot.
This release does not merge multiple accounts or run background provider sync.

## Operator: required hosting

Use ONE persistent FastAPI worker and a persistent runtime volume. Vercel's
current temporary SQLite/process-memory architecture is intentionally refused
for provider connections. CSV and sample data remain available there. Do not
remove that guard to make an unverified connection appear available.
Configure HTTPS at the actual backend and turn off access logs containing OAuth
callback query strings. Never log Authorization headers, token bodies or keys.
A provider invoice import is a user-requested read-only source operation,
not an ArmorIQ-protected agent action. Subsequent MCP execution uses the existing
explicit approval and ArmorIQ/local engine boundary. The known ArmorIQ registry
blocker is unchanged; no provider success claims imply that it is fixed.

## Operator: Zoho OAuth application

1. Follow https://www.zoho.com/invoice/api/v3/oauth/ to register a Server-based
   Application in the Zoho developer console for your data center.
2. Register this exact callback on the actual persistent backend:
   https://YOUR-BACKEND-HOST/api/connections/zoho/callback
   For local development the code accepts loopback HTTP; e.g.
   http://127.0.0.1:8004/api/connections/zoho/callback
3. Set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET and ZOHO_REDIRECT_URI privately in the
   backend environment. The redirect must exactly match the console registration.
   Client registration must support the customer's selected data center.
4. Set FINANCEGUARD_CONNECTOR_KEY to a persistent Fernet encryption key on a hosted
   backend. Never rotate/delete it without migrating existing credentials.
   Local development generates runtime/connector-encryption.key once instead.
5. Restart that backend after local environment changes. Obtain approval before
   applying remote configuration or deployment changes.

No customer key or password is requested for Zoho. Users enter their numeric
Zoho Invoice organization ID, select India/US/EU, and grant only
ZohoInvoice.invoices.READ on the provider consent page. A random expiring state
and HttpOnly browser cookie bind the callback to its initiating browser/owner.
The one-time state is consumed atomically. Offline refresh credentials are
stored encrypted and never returned to the browser or model.

## Customer: Razorpay

Select Test Mode in Razorpay. Open Account & Settings -> API Keys under Website
and app settings. Generate test credentials only if authorized; do not regenerate
an existing integration's keys without understanding its impact. Enter the
rzp_test_ key ID and secret in FinanceGuard. They are encrypted server-side.
This adapter only sends invoice GET requests, although the provider's test key
may itself allow broader actions. Live keys are refused. Follow the official
instructions: https://razorpay.com/docs/api/authentication/

## Customer: Stripe

Choose a sandbox/test environment. Create a restricted TEST API key with invoice
READ permission. Enter the rk_test_ key into FinanceGuard. Publishable, live and
unrestricted secret keys are refused by this new customer connector. It reads
invoice data only; it does not create invoices or payments. The older operator
Stripe sandbox route remains separately restricted and is not customer OAuth.
Official guide: https://docs.stripe.com/keys

## Preview and import

Saving credentials reports SAVED, not successful access. Fetch a preview to
make the real provider request. Preview leaves the workspace unchanged. Review
its invoice count and overdue balance, then confirm. A preview belongs to one
owner/provider/credential version, expires after five minutes and is single use. A changed workspace invalidates
the preview as well.
Reconnect/disconnect invalidates previews. Import invalidates existing approvals.
Disconnect removes encrypted credentials, clears the active source snapshot and
revokes workspace approvals. Provider-wide revocation is separate: revoke keys
or consent in that provider dashboard if desired.

Only INR is accepted. Overdue unpaid/partially-paid rows use the remaining
balance, not the original total. Missing due dates, unknown statuses, invalid
amounts, mixed currencies, duplicate IDs and more than 500 records fail visibly.
No currency conversion or invented dates. Customer labels may fall back to
Customer when the source omits a name. Imports never send email or move money.

## Tutorials and truth boundaries

frontend/guides/index.html is a browser-playable tutorial viewer with three
40-second animations, pause/restart and scrubbing. Original illustrative UI is
based on the official sources above; no personal account footage, secrets or
YouTube clips were used. HyperFrames authoring sources live outside the app
repo in work/financeguard-connection-guides. MP4 export was approved by the user.
All three approved MP4 exports were verified as H.264, 1280x720, 24 fps,
40 seconds each; their decoded frames were inspected. Files are roughly 1 MB
each and the native browser player loaded all three with the correct metadata.
The animations teach setup; they are not evidence of live provider connectivity.

## Validation and remaining work

56 backend tests and five frontend status tests passed. Provider HTTP is mocked
in automated connector tests. Tests cover encryption,
read-only adapter calls, balance normalization, OAuth scope/state/replay, tenant
isolation, preview ownership, reconnect invalidation and secret-free errors.
All three animation runtime/layout/motion/contrast checks pass. Reviewed lint
warnings recommend splitting each small four-step tutorial into sub-compositions;
there are no runtime/layout/contrast errors.

Browser guest access correctly prompts sign-in. A fresh real Firebase login
attempt encountered a browser network failure; the signed-in provider UI and
OAuth consent have not been verified end to end in this run. No Zoho operator
client or customer provider test credentials were available, so no successful
live provider connection is claimed. No remote settings or deployment changed.
