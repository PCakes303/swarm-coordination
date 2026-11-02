# Repository 17 staging status

Experimental single-process coordination scaffold deployed to the public repository. All 18 files match the master staging packet. CI passed on Python 3.10, 3.11 and 3.12 (17 tests): https://github.com/PCakes303/swarm-coordination/actions/runs/41417719239. Master control-plane validation passed: https://github.com/PCakes303/agent-intelligence-ecosystem/actions/runs/41416825323. This validates the master registry and staging control plane; the repository-local Python test matrix runs after deployment. Includes validated task declarations, deterministic candidate selection, policy-gated idempotent submission, dispatch and acknowledgement binding, bounded retry attempts, lease-expiry recovery (including stale acknowledgement rejection), completion/failure transitions, optional audit events, AIX mapping guidance, JSON Schema, tests and Python 3.10–3.12 CI.

The initial vertical slice is a coordinator library with injected candidate resolver and dispatch adapter. It is not a network service, distributed scheduler or consensus protocol. State and idempotency records are in-memory and volatile. No cryptographic caller authentication, durable state, cross-replica replay protection, distributed locking, federation, consensus, production AIX codec integration or production adapters are implemented.

Dependencies on Swarm Runtime, AIX Core, Agent Discovery Network and Agent Capability Registry remain `declared`, not `tested`.

Next: deploy and test the scaffold; then build authenticated transport integration, durable task state, cross-repository AIX/discovery/capability fixtures and multi-node recovery tests.
