# Activity counter and session behavior

Activity counts the latest 100 events for the current owner, across engines.
The status dropdown filters only the displayed list. Completed counts ALLOWED;
blocked counts BLOCKED. SDK-reported verified executions require ALLOWED,
engine ARMORIQ, and boolean verified exactly true. Approval, holds, errors,
local blocks and telemetry ingestion never satisfy this count.

SDK 0.6.10 assigns verified=True when constructing an invocation result after
proxy response handling. FinanceGuard reports this as the SDK assertion, not
independent proof of a dashboard decision or cryptographic verification. The
backend also requires successful tool output and the matching workspace summary.

Startup now loads an existing workspace first. Only HTTP401 starts a sample;
network/server errors never replace the owner. Repeated /api/demo calls reuse a
valid guest. Guest expiry or process-memory loss can still require a new session.

Vercel activity storage is temporary SQLite and is not durable across workers
or deployments. This patch does not migrate to a cloud database or solve shared
approval/session storage. Stable signed-in ownership and durable shared storage
are separate deployment work. No history from another owner is exposed.

Regression tests cover repeated startup, expired-session isolation, preservation
of recorded activity, counter provenance and failure paths that must not reset
sessions. They do not establish live ArmorIQ execution or dashboard visibility.
