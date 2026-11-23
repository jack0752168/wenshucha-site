# Verified, one-time MCP free trials

Public entry: `/mcp/claim/`. Required: name, company, phone, email, consent.
Email ownership is verified by a ten-minute, six-attempt OTP. Phone, name and company
remain self-reported. Canonical email and phone are each unique for trial issuance.
Returning owners can recover their original key by verifying the same email; expiry
and quota are not reset. A single calendar month is granted, clamping month-end days.

The loopback-only cloud service (`127.0.0.1:8791`, `wsc-mcp-trial.service`) stores an
encrypted private SQLite ledger. An authenticated outbound mini worker sends OTP
email and atomically issues a standard free key (1,000 calls / 100 body reads / 30 rpm)
into the existing MCP key registry. Existing MCP and Elasticsearch are not restarted.
SMTP credentials stay on the private mini, not the public cloud. Secrets must never
be committed. Config files are mode 600, private directories 700.

A durable CRM outbox is consumed by `crm_sync.py` on the existing CRM host, using a
separate worker credential. Leads are merged by email, phone or exact company name
into `sinoverdict-crm/pipeline.json`, preserve paid/outreach stages, and never enroll
new contacts into automated cold emails. Replays are idempotent by trial ID. Key
values are not put into CRM: only a mask, plan, issuance day and expiry are stored.
`crm_store.py` provides locked atomic merge logic to the CRM's existing `save` method.

Deployment requires a protected config on mini containing `url`, `token`, `smtp`,
and `mcpRoot`. Cloud environment requires three independent random secrets:
`WSC_TRIAL_SECRET` (32 bytes hex), `WSC_TRIAL_WORKER_TOKEN`, `WSC_TRIAL_CRM_TOKEN`.
The public cloud has no SMTP password. Origin validation, SameSite HttpOnly Secure
cookies, per-email/IP/global mail limits, encrypted payloads and authenticated job
leases are enforced. No marketing subscription or payment action is part of signup.

Tests: `node --test ops/mcp-trial/test.mjs` and
`python3 -m unittest discover -s ops/mcp-trial -p test_crm.py`.
Live acceptance additionally needs mailbox receipt, public issuance, all four MCP
tools, CRM readback, and evidence that paid customer entries remain unchanged.
