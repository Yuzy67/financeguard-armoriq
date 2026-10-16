# Submission pack

## Form fields

- Team: Anuj A Shetty and Yuvraj Singh (confirm the exact registered spelling).
- Project: FinanceGuard.
- Repository: https://github.com/Yuzy67/financeguard-armoriq
- Live demo: https://financeguard-armoriq.vercel.app
- Demo video: PENDING - insert the actual unlisted 3-5 minute walkthrough URL.
- ElevenLabs integration: Not used.
- Social post: PENDING - insert the actual X or LinkedIn post URL after publishing.

## How we use ArmorIQ (use after the actual demo passes)

FinanceGuard uses ArmorIQ to enforce approved intent for MCP tool execution.
A user approves one invoice operation. Our Python backend starts an SDK session,
captures that plan, obtains its intent token, checks permission, and invokes the
approved MCP tool through ArmorIQ. The actual SDK response supplies its
verification status. An attempted refund under a summary-only plan is rejected
by SDK intent binding with IntentMismatchException before proxy invocation.
The session records the checks and actual tool report and flushes observability.
Ingestion receipts and SDK trace IDs are kept distinct from local activity IDs.
We claim cloud-console visibility only after viewing the actual session there.

## Social copy (draft; not published)

Built FinanceGuard for #FlowStateHackathon.

An MCP finance assistant for invoice work with explicit authority.

Approved: summarize overdue invoices.
Outside the approved plan: refund simulation blocked.

Built with ArmorIQ SDK intent checks and a source-labeled action trail.
No real payments or emails. Created by Anuj A Shetty and Yuvraj Singh.

https://github.com/Yuzy67/financeguard-armoriq
@ArmorIQ

Attach the real walkthrough once it is recorded. Do not imply the final
production/console demo has passed while the configuration gate remains open.

## Final readiness gates

- [ ] Replacement key belongs to the intended org and exists privately in both runtimes.
- [ ] Current MCP URL is reachable, registered in that org, and matches MCP_SERVER_URL.
- [ ] Local real-provider demo passes; safe output and refund denial preserved.
- [ ] Provider accepts observability and actual session is visible in the console.
- [ ] Vercel real ArmorIQ actions pass; operator sample data matches MCP output.
- [ ] Test from a separate device/network (not yet performed by this workspace).
- [ ] Record actual MCP, Policy Studio, and Observability screens without secrets.
- [ ] Publish unlisted 3-5 minute video and check viewer access.
- [ ] Publish founders' selected social post and add its real URL.
- [ ] Verify final form deadline/timezone and submit.

Official page: https://armoriq.ai/hackathons/flow-state
It lists submissions closing October 17, uses UTC, and does not provide an exact
hour in the public page inspected October 16. The supplied 11:59 PM IST and
October 17-21 judging window need confirmation from the final official form or
organizer announcement. Do not infer them from the general event page.
