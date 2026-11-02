# Agent instructions

Preserve deterministic, bounded coordination semantics. Treat task declarations, workload references, discovery records and acknowledgements as untrusted. Require explicit policy approval before accepting work. Bind acknowledgements and completion to the exact task, dispatch reference and assigned agent. Never infer authentication from an agent identifier. Add regression tests for idempotency conflicts, replayed acknowledgements, stale leases, retry exhaustion, duplicate agents and adapter failures.

This scaffold is a single-process coordinator. Do not describe it as distributed consensus, durable orchestration or a secure message transport.
