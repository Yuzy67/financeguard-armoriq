# Saved assistant permissions

After sign-in, new users choose a mode for each supported invoice task. Existing
users open **Assistant → Saved permissions**. All tasks default to **Ask me**.

- **Automatic with ArmorIQ:** explicit standing consent for this account's current
  and future imports. A verified sign-in email is required. When the user requests
  a task, the server creates a short-lived, snapshot-scoped SDK plan if needed,
  checks ArmorIQ, then invokes the MCP through ArmorIQ only when allowed.
- **Ask me each time:** chat displays a single-use approval card with **Approve &
  run** and **Don't approve**. Declining never invokes a tool or fabricates a
  provider decision.
- **Never allow:** blocks chat and manual execution paths. Clients cannot use the
  preferences API to enable refunds, transfers, deletion or sending emails.

Account choices are stored in FinanceGuard's existing workspace database. They
are **not** remote ArmorIQ organization-policy edits. Real SDK plan issuance and
per-action checks are the provider integration; the existing MCP-targeted policy
remains authoritative. No new agent, MCP registration or policy is created.

The installed SDK's native hold handler can create/reuse a provider delegation.
A held action is returned as **HELD**, with the real delegation UUID when exposed;
no MCP invocation is made. Review it in ArmorIQ Held Actions, then request the same
task again before the five-minute plan expires. FinanceGuard cannot approve a
provider hold. A new or expired plan may require another provider review.

Saving new choices revokes existing plans and pending chat cards. Revoke approvals
also resets automatic choices to Ask. Consent versions are checked inside the
owner lock at plan creation and execution, so a concurrent revocation cannot
reuse stale automatic consent. Invoice changes invalidate snapshot-bound plans;
standing consent can create a new one only after another user request.

On temporary Vercel storage, choices can reset across workers or deployments.
The UI states this limitation. Missing permissions fail closed to asking again.
Durable cross-instance persistence is not introduced by this change.

The local regression suite covers saved scope, owner isolation, malicious task
names, no-consent payloads, explicit refusal, revocation, stale consent, provider
outages, native SDK holds and no local fallback. These tests mock cloud responses;
they do not establish live deployment or dashboard acceptance.
