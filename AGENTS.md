# Agent instructions

- Preserve deterministic, bounded coordination semantics. Treat task declarations, workload references, discovery records and acknowledgements as untrusted.
- Require explicit boolean `True` policy approval before accepting work; missing, false, non-boolean or raising callbacks deny.
- Bound candidate resolver enumeration (256 by default), task retention and attempt budgets; never materialize an unbounded resolver iterable.
- Reject boolean and non-finite lifecycle timestamps.
- Bind acknowledgements and completion to the exact task, dispatch reference and assigned agent. Never infer authentication from an agent identifier.
- Treat leases as recovery deadlines, not proof of remote worker termination. Require fencing or idempotent side effects before production retry.
- Audit callback failure must fail closed. Preserve state consistency when dispatch, audit or recovery fails.
- This scaffold is a single-process coordinator. Do not describe it as distributed consensus, durable orchestration or a secure message transport.
- Add regression tests for idempotency conflicts, replayed acknowledgements, stale leases, retry exhaustion, duplicate agents, candidate limits, timestamp validation and adapter failures.
- License remains pending review; do not add a license file or infer one.
- Run `python -m unittest discover -s tests -v` before proposing changes.
