# Security Policy

This repository is an experimental, single-process in-memory task coordinator, not a trusted distributed control plane.

## Reporting

Do not publish exploitable vulnerabilities, credentials, tokens, or private operational data in public issues. Use GitHub private vulnerability reporting or a private security advisory if enabled for this repository. A dedicated private reporting address is not published here; if private reporting is unavailable, the owner must configure an owner-approved private channel before production use.

## Trust and lifecycle boundaries

- Policy admission accepts only explicit boolean `True`. The supplied requester identifier must originate from a trusted upstream; this package does not authenticate it.
- Candidate discovery is advisory. Candidate records do not prove identity, health, capability implementation or authorization.
- Candidate enumeration is bounded (256 by default); task count, attempt count, identifier sizes and lease duration are bounded.
- Lifecycle timestamps must be finite numeric values; boolean and non-finite values are rejected.
- Acknowledgements and completion are bound to task, dispatch reference and assigned agent, but callers/messages are not cryptographically authenticated.
- Idempotency and leases are process-local and volatile. They do not prevent replay across restarts or coordinator replicas.
- Dispatch adapters must provide authenticated, integrity-protected delivery and enforce authorization.
- Workload references are opaque; this package does not fetch or execute workload content.

Do not expose coordinator methods directly to untrusted networks. Production use requires authenticated transport, durable shared state, distributed consistency, replay protection, real identity/policy/audit integrations and adversarial review.
