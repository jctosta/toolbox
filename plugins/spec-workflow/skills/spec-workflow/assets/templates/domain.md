# Domain: <product name>

| Field | Value |
|---|---|
| updated | <YYYY-MM-DD> |

## Glossary
| Term | Definition | Notes |
|---|---|---|
| <Term> | <one sentence, in the user's words> | <synonyms to avoid, disambiguation> |

## Entities and relationships
```mermaid
erDiagram
    ENTITY_A ||--o{ ENTITY_B : "verb"
    ENTITY_A {
        string status
    }
```

## Lifecycles
### <Entity>
```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> COMPLETED
    PENDING --> REJECTED
```
Transition rules:
- PENDING → COMPLETED: <who/what triggers it>

## Invariants
- INV-01: <rule that must always hold, entity-level, testable>
