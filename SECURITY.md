# Security notes

Do not commit .env, armoriq.yaml, credential JSON, runtime signing keys, or
workspace SQLite files. Public Firebase web configuration is not an Admin SDK
credential. It never authorizes server invoice access by itself.

An ArmorIQ key appeared in an earlier upstream .env.example commit. That key
must be revoked by its account owner. Current source removal does not scrub
history. Coordinate any Git history rewrite with both maintainers; do not
force-push it as part of a frontend deployment.

Only synthetic data is used for the public demo. Importing invoices requires
Firebase identity verification. MCP data access requires a short-lived signed
owner/action/dataset credential. Reading tool discovery is public by design;
tool execution is protected. Refund/transfer/deletion tools cannot move money.

ArmorIQ telemetry report output is deliberately limited to execution status;
full invoice contents and workspace credentials are not uploaded as trace
outputs. Cloud ingestion and console visibility must be checked independently.

Hosted state is temporary on Vercel. Do not use this hackathon build as a
production financial system or assume multi-instance persistence/revocation.
