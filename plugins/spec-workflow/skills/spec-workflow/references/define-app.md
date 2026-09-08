# Phase: define-app

Produces `docs/product/product.md` and `docs/product/domain.md`. These are the shared context every feature phase reads first, so they're worth getting right — but they're also living documents, revised when features teach you something.

## Inputs

- The conversation: what the user wants to build, for whom, why.
- Anything already in the repo: README, existing docs, existing code structure (for brownfield).
- For brownfield, also skim the main modules and any existing tests to infer capabilities that already exist. Mark them `(existing)` in the capability map.

## Interview

Ask before writing. Cap at 6 questions per round, two rounds maximum; after that, write with explicit assumptions. Questions that matter most:

1. Who are the actors? Not "users" — the distinct roles that interact with the system, including external systems and scheduled jobs.
2. What is the one job the product must do well? If everything else were cut, what stays?
3. What is explicitly not this product (non-goals)? People rarely volunteer these; ask directly.
4. Constraints that shape everything: stack, hosting, compliance regime (LGPD/HIPAA/none), budget of time, must-integrate systems.
5. What does "done for v1" look like? A demo scenario in one paragraph.
6. Vocabulary: what words does the user already use for the things in this domain? Use their words in the glossary.

Don't ask about features yet. Features fall out of actors + jobs + constraints; asking for a feature list first produces a wishlist, not a product.

## Writing product.md

Use `assets/templates/product.md`. Section notes:

- **Vision** — one paragraph, no adjectives that can't be tested. "Fast" is not a vision; "an owner is told a task is due before it passes, without opening the app" is.
- **Actors** — one line each: who they are and what they want from the system. External systems count.
- **Jobs to be done** — 3 to 7. Each one is something an actor accomplishes, phrased as an outcome. These become the spine of the capability map.
- **Non-goals** — explicit. Include things the user was tempted by and rejected, with a short reason.
- **Constraints** — technical, legal, operational. Anything a feature must respect without being told.
- **Capability map** — the domains the system is made of, each with a one-line responsibility. 4 to 10. These become the `Capability:` field in every feature brief, and later the natural place for a living spec per domain if the project grows into one.
- **Feature roadmap** — the initial list of features, each with a proposed slug, capability, rigor level guess and priority. This is the only place where the roadmap lives until features get their own folders; keep it ordered. Mark the smallest set that makes the v1 demo scenario work as `v1`.
- **v1 demo scenario** — the paragraph from question 5. It's the acceptance test for the roadmap: every step of the scenario must map to a `v1` feature.

## Writing domain.md

Use `assets/templates/domain.md`. It's a conceptual model, not a schema — no column types, no indexes.

- **Glossary** — every noun that appears in product.md and will appear in specs. One definition each, in the user's words. Disambiguate synonyms explicitly ("Request and Ticket are the same thing; use Request").
- **Entities and relationships** — a Mermaid `erDiagram` with entity names from the glossary and relationship verbs. Cardinality matters; attributes only where they carry business meaning (status, deadline), not for completeness.
- **Lifecycles** — a Mermaid `stateDiagram-v2` for each entity that has a status. State names become vocabulary in scenarios (`status PENDING`), so pick them here and never invent new ones in a spec.
- **Invariants** — rules that must always hold regardless of feature ("a subject has at most one PENDING request"). Specs reference these instead of restating them.

## Gate

Report each item as pass/fail:

- [ ] Every actor in product.md appears in at least one job to be done.
- [ ] Every step of the v1 demo scenario maps to a feature marked `v1` in the roadmap.
- [ ] Every capability in the capability map has at least one roadmap feature (or is marked `(existing)` for brownfield).
- [ ] Every noun used in the roadmap feature titles is defined in the glossary.
- [ ] Every entity with a status has a lifecycle diagram, and lifecycle state names are UPPER_SNAKE.
- [ ] The diagrams in domain.md parse: `npx -y @probelabs/maid docs/product/domain.md` (spec_lint only covers feature folders).
- [ ] Non-goals has at least one entry that was an explicit rejection, with reason.
- [ ] No section was deleted from either template; empty sections say `None — <why>`.
- [ ] Assumptions the user didn't confirm are marked `(assumed)` inline.

Then stop. Summarize: actors, jobs, capability map, the v1 feature set, and the list of `(assumed)` items to confirm. Suggest which feature to explore first (usually the one the demo scenario depends on most).
