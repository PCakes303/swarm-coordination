# Coordination contract v1

## Purpose and boundary

The coordinator accepts a task request, obtains a fail-closed policy decision, resolves eligible candidate agents, dispatches to one candidate, binds acknowledgement and completion to that assignment, and retries within a fixed attempt budget. The implementation is single-process and in-memory.

## Task request

A request contains bounded `task_id`, `idempotency_key`, trusted-upstream `requester_id`, exact `capability_id`, opaque `workload_ref`, and `max_attempts` (1–5). Workload bytes and credentials are not carried in the request.

An identical idempotency key and identical request returns the original task record. Reuse of the key with a different request is rejected. Idempotency is limited to this coordinator process lifetime.

## Candidate selection

The injected resolver returns candidate agent descriptors. The coordinator validates identifiers, filters to the exact requested capability, removes duplicate agent identifiers and sorts deterministically by agent identifier. Discovery and capability claims are advisory until authenticated and independently verified.

## Lifecycle

`queued → assigned → acknowledged → running → succeeded`

Failure or lease expiry transitions the task to another bounded attempt, or to `failed` when the attempt budget is exhausted. Each attempt has a unique deterministic dispatch reference derived from task ID and attempt number. Acknowledgement and completion must match the active dispatch reference and selected agent.

A lease is a recovery deadline, not proof of remote termination. Retrying after expiry may overlap an old worker if the transport/executor cannot fence it. Production adapters must implement fencing or idempotent side-effect semantics.

## Policy and audit

A policy callback must return exactly `True`; absent, false or raising callbacks deny submission. The optional audit callback receives bounded lifecycle metadata only. If configured, audit failure prevents or aborts the relevant transition.

## AIX extension mapping

AIX remains a semantic extension layer over existing transports. An adapter may map the task request to the AIX Core `task.request` envelope, using task identifiers, idempotency key, capability requirements, input references, sender/recipient security context and provenance references. Acknowledgement and status/result messages should use the AIX task lifecycle vocabulary and the pinned AIX schema once a cross-repository profile is tested. This scaffold does not import or implement AIX codecs and does not claim conformance.

## Durability and distribution

The included store is process-local. Restart loses task state, leases and idempotency keys. Multiple coordinator instances do not share locks or state. No consensus, replicated log, exactly-once delivery or exactly-once execution is provided.
