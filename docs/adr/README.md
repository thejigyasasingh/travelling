# Architecture decision records

Six decisions that shaped this system, each written down because the reasoning
is not recoverable from the code. The code shows *what*; these say *why*, and
more usefully, **what would have to change to make a different answer right**.

They are not a design document. Everything here was contested, and each one has
a cost written down next to its benefit.

| # | Decision | Why you would care |
|---|---|---|
| [0001](0001-modular-monolith.md) | A modular monolith, boundaries enforced | Why this isn't microservices, and what the exit looks like |
| [0002](0002-money-as-integer-minor-units.md) | Money as integer minor units | Why every amount field ends in `_minor` |
| [0003](0003-uuidv7-primary-keys.md) | UUIDv7 primary keys | Why not `bigserial`, and why not `uuid4` |
| [0004](0004-half-open-date-ranges.md) | Half-open stay ranges `[in, out)` | Why a one-night booking sends a two-day range |
| [0005](0005-transactional-outbox.md) | Events via a transactional outbox | Why consumers must be idempotent |
| [0006](0006-refresh-token-rotation.md) | Rotating refresh tokens | Why every client implements single-flight refresh |

## The rest of the reasoning is in the code

These six are the decisions with consequences spread across the whole system.
The narrower ones are documented where they apply, in the module or file they
constrain — the rate-limit policy in `middleware/rate_limit.py`, the caching
policy in the Flutter `CatalogRepository`, the notification ordering in
`SendNotificationUseCase`. Reading a module's docstring is meant to be enough
to change it safely.

## Writing a new one

Number it, and answer four questions: what forced the decision, what was
decided, what it costs, and what would change it. If the last question has no
answer, the decision is probably a preference — which is fine, but it does not
need a record.
