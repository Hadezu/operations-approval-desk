# Approval workflows that preserve accountable decisions

## Business problem

Operations teams need to know who changed a request, which version they reviewed and whether another reviewer acted first.

## Implemented solution

Implemented a Django/PostgreSQL review queue with team-scoped access, preserved proposal history, exact-version decisions and downloadable audit evidence.

## Inspect the result

The English and Polish guided demos expose the workflow. Tests exercise stale decisions, access boundaries and rollback; the verification document records the executed scope.

[Implementation and demonstration](../README.md) · [Recorded verification](VERIFICATION.md)

## Apply this to your business

The same mechanisms can support a new application, an integration or an improvement to your existing system. Scope and acceptance checks are agreed around your workflow. **[Discuss your project](https://work.matiushkin.com/en/contact)**.

[Requirement research and project context](REQUIREMENT-RESEARCH.md) · [Verification scope](../PRESENTATION-SCOPE.md)
