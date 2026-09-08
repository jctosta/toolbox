# Phase: refine

Produces `docs/features/<slug>/spec.md`: the behavioral contract, written as requirements with use-case flows. This is the artifact the human validates most carefully, so optimize it for reading: short requirement statements, concrete scenarios, no implementation.

## Inputs

- `brief.md` — must exist and be approved (no blocking questions). If it isn't, stop and say so.
- `docs/product/domain.md` — entity names, lifecycle states and invariants are vocabulary; use them verbatim.
- `docs/product/product.md` — constraints that apply without being restated (compliance regime, etc.).
- Existing `spec.md` files in features under the same capability — to avoid contradicting them and to reuse phrasing.

## Method

Work requirement by requirement. For each:

1. **State it** in one sentence with one RFC 2119 keyword. Subject is "The system"; object is observable behavior. `The system SHALL reject a submission when the subject already has a PENDING request.`
2. **Name actors, preconditions, postconditions** in the table under the requirement statement. Preconditions reference lifecycle states and invariants from domain.md. Postconditions describe the observable end state — what changed that an outsider could check.
3. **Write the main flow** as `S-NN.1`: the path where everything goes right. GIVEN sets up state, WHEN is one actor action or one event, THEN/AND list every observable effect — the response, the state change, the notification, the audit record. If a THEN can't be observed from outside the system, it's implementation; move it to design.
4. **Write alternative flows** `S-NN.2…`: legitimate paths that end in a different valid outcome (duplicate rejected, partial result, user cancels).
5. **Write exception flows**: things going wrong outside the actor's control (dependency fails, timeout, concurrent edit). For full rigor every requirement needs at least one exception flow; for lite, every requirement that involves any external effect (notification, integration, persistence beyond the request) needs one.
6. **Check the requirement against the brief's scope.** If the flow you're writing is out of scope, delete it. If it's in scope but not in the brief, it's scope creep — flag it in the review message instead of adding it silently.

After all requirements:

7. **Cross-cutting section**: non-functional constraints that apply to the whole feature and are testable — response time bounds, retention, auditability, idempotency, concurrency guarantees. Each one phrased so a test could check it.
8. **Data and state changes**: which entities are created/modified, which lifecycle transitions occur (names from domain.md), which invariants are relied upon or introduced. New states or invariants mean domain.md must be updated — do that update in the same turn and mention it.
9. **The upset test**: ask yourself which single case, if broken in production, would upset the user most. Find its scenario. If it doesn't exist, write it now.

## What stays out

Library names, framework names, HTTP verbs and paths, table or column names, class or function names, queue names, "call X service", retry mechanics ("retry 3 times with backoff" is design; "the request remains PENDING and delivery is re-attempted" is spec). The lint has a forbidden-word list; a hit means rewrite the sentence around the observable effect.

Also out: UI copy, layout, colors. Those go in design.md under UI notes if they matter.

## Numbering

`REQ-NN` sequential from 01. `S-NN.M` sequential within the requirement, main flow always `.1`. Never renumber an existing ID; if a requirement is removed after review, keep the heading with `(removed — reason)` so references in tests.md don't dangle.

## Writing spec.md

Use `assets/templates/spec.md`. The scenario heading format is fixed because the lint parses it:

```
### S-01.2 Alternative — duplicate request
### S-01.3 Exception — notification delivery fails
```

The word after the ID is the flow kind (`Main flow`, `Alternative`, `Exception`), then an em dash, then a short name.

## Gate

- [ ] `feedback.md` has no open items on this phase's input artifact; open items on `spec.md` were addressed in this run.
- [ ] Every REQ has exactly one keyword (SHALL/MUST/SHOULD/MAY) and states one behavior.
- [ ] Every REQ has a `Main flow` scenario numbered `.1`.
- [ ] Rigor full: every REQ has an `Exception` flow. Rigor lite: every REQ with an external effect has one.
- [ ] Every scenario has at least one GIVEN, exactly one WHEN, at least one THEN.
- [ ] Every THEN/AND line is observable from outside the system.
- [ ] Preconditions and state references use lifecycle state names from domain.md verbatim.
- [ ] Nothing in spec.md is out of the brief's scope; anything added beyond the brief is listed in the review message as proposed scope change.
- [ ] Cross-cutting section has at least one testable constraint or says `None — <why>`.
- [ ] Data and state changes section lists every entity touched; domain.md updated if new states/invariants.
- [ ] The "upset test" case is identified in the review message with its S-ID.
- [ ] `python scripts/spec_lint.py docs/features/<slug>` reports no errors; warnings are acknowledged with reasons.

Then stop. In the review message: list REQ IDs with one-line titles, the upset-test scenario, scope changes proposed, assumptions. Ask the user to review the spec *as if it were the only thing they'll ever get to read about this feature* — because for the test-spec phase, it is.
