# Security

This repository is an experimental, in-memory task coordinator, not a trusted distributed control plane.

- Policy admission fails closed. The supplied principal identifier must originate from a trusted upstream; this package does not authenticate it.
- Candidate discovery is advisory. Candidate records do not prove identity, health, capability implementation or authorization.
- Acknowledgements and completion are bound to task, dispatch reference and assigned agent, but the coordinator does not cryptographically authenticate the caller or message.
- Idempotency and leases are process-local and volatile. They do not prevent replay across restarts or across coordinator replicas.
- Dispatch adapters must provide authenticated, integrity-protected delivery and enforce authorization.
- Workload references are opaque; this package does not fetch or execute workload content.

Do not expose coordinator methods directly to untrusted networks. Production use requires authenticated transport, durable shared state, distributed consistency, replay protection, real identity/policy/audit integrations and adversarial review.
