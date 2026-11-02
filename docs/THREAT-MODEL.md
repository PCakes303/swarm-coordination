# Threat model

## Assets and threats

The coordinator handles task identifiers, requester identifiers, capability requirements, workload references, candidate metadata, dispatch references and lifecycle state. Threats include malformed requests, idempotency-key collisions, unauthorized submissions, candidate poisoning, forged/replayed acknowledgements, stale workers, retry storms, adapter failures, audit failures and state loss.

## Controls in this scaffold

- Strict bounded task fields and attempt count.
- Fail-closed policy callback.
- Bounded in-memory task count and retry attempts.
- Deterministic candidate ordering and duplicate-agent filtering.
- Idempotency conflict detection within process lifetime.
- Acknowledgement/completion bound to task, active dispatch reference and assigned agent.
- Explicit lease expiry and manual recovery operation.
- Optional lifecycle audit callback with fail-closed transition behavior.

## Not implemented

No caller authentication, cryptographic message verification, authenticated transport, durable idempotency, distributed locking, replicated state, consensus, cross-replica replay protection, endpoint health checks, capability attestation, exactly-once delivery or production AIX integration exists.

Lease expiry does not terminate a remote worker. A retry can overlap an old attempt. Production execution must use fencing tokens or idempotent side effects, durable shared state, authenticated adapters and adversarial testing.
