# Spec: <feature title>

| Field | Value |
|---|---|
| slug | <kebab-slug> |
| status | draft \| approved |
| brief | ./brief.md |

## Requirements

## REQ-01: <short title>
The system SHALL <one observable behavior>.

| Actors | Preconditions | Postconditions |
|---|---|---|
| <actor>, <actor> | <state, using lifecycle names from domain.md> | <observable end state> |

### S-01.1 Main flow — <name>
- GIVEN <state>
- WHEN <one action or event>
- THEN <observable effect>
- AND <observable effect>

### S-01.2 Alternative — <name>
- GIVEN <state>
- WHEN <action>
- THEN <different valid outcome>

### S-01.3 Exception — <name>
- GIVEN <state>
- WHEN <something outside the actor's control fails>
- THEN <how the system leaves things observable and recoverable>

## REQ-02: <short title>
...

## Cross-cutting constraints
- X-01: <testable non-functional constraint, e.g. "A submission is acknowledged within 2 seconds at p95">
- None — <why> (if truly none)

## Data and state changes
- Entities created: <entity>
- Entities modified: <entity> — <which fields/aspects, in business terms>
- Lifecycle transitions used: <ENTITY: STATE → STATE>
- Invariants relied on: INV-NN
- Invariants introduced: None | INV-NN (added to domain.md)

## Removed
- None
