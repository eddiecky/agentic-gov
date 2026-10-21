# Application Architecture Principles

Evaluate every solution submission against the principles below. For each one,
decide whether the submission PASSes, raises a CONCERN, or FAILs, and cite the
evidence from the submission.

## 1. Separation of concerns

Components have a single, well-defined responsibility. Business logic is not
mixed with transport, persistence, or presentation code.

## 2. Loose coupling, high cohesion

Modules depend on abstractions, not on each other's internals. A change inside
one module must not force changes in unrelated modules.

## 3. Statelessness of services

Application services hold no session state between requests. State lives in
explicit stores (database, cache, queue) so any instance can serve any request.

## 4. API-first design

Every capability is exposed through a versioned, documented API contract.
Internal consumers use the same contracts as external ones.

## 5. Idempotency and safe retries

Operations that mutate state are idempotent or carry idempotency keys, so
retries after timeouts cannot cause duplicate effects.

## 6. Explicit error handling

Failure modes are designed, not accidental. Errors carry enough context to
diagnose, and callers can distinguish retryable from permanent failures.

## 7. Observability by design

Services emit structured logs, metrics, and traces correlated by request id.
It is possible to answer "what happened to request X" without code changes.

## 8. Twelve-factor configuration

Configuration comes from the environment, never from code or committed files.
Secrets are never stored in source control.

## 9. Data ownership

Each data entity has exactly one owning service. Other services access it
through the owner's API or events, never through its database.

## 10. Testability

The design allows business logic to be tested without infrastructure.
External dependencies can be substituted in tests.
