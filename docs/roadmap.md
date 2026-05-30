# PrintStash Roadmap (Post-Stage 4)

This roadmap tracks the next milestones after Stage 4 completion.

## R1 — Provider Maturity (Short term)

- Bambu LAN upload/send parity with provider-safe guardrails
- Provider-level health diagnostics endpoint
- Mixed-fleet resilience tests under disconnect/reconnect storms
- Frontend provider capability UX polish (action gating/tooltips)

## R2 — Operations Hardening (Short/medium term)

- Redis-backed pub/sub for multi-process `PrinterHub`
- Background jobs for retention/GC decoupled from request lifecycle
- Structured metrics (prometheus-style counters + latency histograms)
- Backup/restore smoke checks and disaster-recovery runbook

## R3 — Fleet & Scheduling (Medium term)

- Optional routing strategies (manual/default-printer/least-busy)
- Queue visibility with provider-normalized job model
- Printer maintenance windows + soft-drain mode
- Alerting hooks (webhook/email) for offline/error state transitions

## R4 — Optional Cloud/Enterprise Adapters (Longer term, still opt-in)

- Bambu cloud adapter (separate from LAN provider)
- Multi-tenant org/workspace routing
- Org-aware storage namespace and audit partitioning
- Advanced S3 lifecycle policy templates
