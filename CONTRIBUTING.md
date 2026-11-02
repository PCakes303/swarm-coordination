# Contributing

Run `python -m unittest discover -s tests -v`. Add tests for every lifecycle transition, retry path, policy denial, audit failure and recovery boundary. Keep candidate discovery, dispatch transport, identity, policy and audit behind injected interfaces. Preserve bounded task counts and attempt counts. Never mark a dependency `tested` without reproducible cross-repository evidence.
