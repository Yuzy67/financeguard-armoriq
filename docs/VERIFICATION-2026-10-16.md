# Verification report - 16 October 2026

## Code and SDK instrumentation

The updated implementation has 22 automated tests. SDK session tests run the
installed production SDK against mocked HTTP responses. They check actual span
structure and shipping, including plan, policy allow/deny and tool.report,
accepted/rejected delivery, same-session correlation, wrong-org/stale-origin
rejection, and policy outages that must not execute a tool. These are unit
contracts, not proof of a real external trace.

## Browser checks performed locally

- Four routes show separate views and update aria-current navigation.
- Sample plan approval, actual local MCP summary, blocked refund, and audit row.
- Summary uses the real sample invoice total: INR 88,000 across three overdue rows.
- Audit filtering shows only blocked actions when selected.
- Mobile 390px viewport keeps navigation visible and has no page-wide overflow.
- Reduced-motion CSS is present. Loading/error/blocked states are distinct.

## Current real-provider check

Running run_financeguard_demo.py with the existing private configuration exits
nonzero before tool execution because its actual bootstrap organization differs
from the requested team organization. No new live trace delivery or console
visibility is claimed. Use tools/check_setup.py after updating private settings.

## Remaining external gates

Correct organization key locally and on Vercel; current healthy registered MCP
origin; ingestion acceptance; actual console inspection; cross-device/network
verification; 3-5 minute recording/upload and social publication. See
SUBMISSION.md for exact unchecked gates. Do not fill missing links with examples.

## Deployed verification after the repair

GitHub Actions verify job passed on Ubuntu/Python 3.12, and Vercel reported the
production deployment completed. The actual public UI passed summary approval,
real MCP execution returning INR 88,000, refund blocking, and the source-labeled
action trail. An existing Firebase test session was accepted by the backend.
These deployed actions ran in LOCAL_POLICY mode, not ArmorIQ mode.
The public health route returned HTTP 200 with armoriq_configured=false.
That missing production key remains a real setup gate, not a verified cloud run.
