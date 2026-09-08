# Phase: design

Produces `docs/features/<slug>/design.md`: how the parts of the system interact to satisfy each scenario, which contracts change, and which decisions were made. This is where implementation vocabulary is allowed — and where it must stay.

Mandatory for rigor full. For lite, run it when a scenario involves more than one component or any external system; otherwise skip it and say so in the handoff.

## Inputs

- `spec.md` — approved. Every diagram references its scenarios.
- `docs/product/product.md` constraints (stack, hosting, compliance).
- The codebase, for brownfield: identify the actual components, modules and external services the flows will touch. Name them as they exist, not as you'd like them to be.

## Method

1. **Components.** List the participants that will appear in diagrams: UI, API, services/modules, stores, external systems, schedulers. One line each with responsibility. For brownfield, path to the module. New components are marked `(new)`.

2. **Sequence diagrams.** One Mermaid `sequenceDiagram` per main flow, and one per exception flow that changes the interaction (a dependency failing, a timeout). Alternatives that are just a different branch go into the main flow's diagram with `alt`/`else`. Each diagram starts with a comment line the lint reads:

   ```
   %% covers S-01.1, S-01.2
   ```

   Participants use the component names from step 1. Messages carry the meaningful payload in words, not types (`set due time on task (task_id)`, not `PUT /tasks/{id}/due {…}` — the endpoint goes in Contracts). Show the state transition as a note when one happens (`Note over Store: status → PENDING`). Show the async boundary explicitly when something is queued.

3. **Contracts.** Every interface that is created or changed: API endpoints (method, path, request/response shape — an OpenAPI fragment or a typed schema is fine), events published/consumed (name, payload), database changes (new entities/columns as a migration sketch), configuration keys, permissions. If nothing changes, say `None — <why>`. Each contract lists which REQ it serves.

4. **Decisions.** `D-NN` entries in ADR-short form: context (one line), decision (one line), alternatives considered (at least one, with why not), consequences (what this makes easier and harder). Only real decisions — a choice with no credible alternative isn't a decision, it's a fact; put it under Components.

5. **Risks.** `[risk] → mitigation` pairs. Include at least: what happens on partial failure mid-flow, and what's the rollback story. For full rigor, also data migration risk and backward compatibility.

6. **UI notes** (if the feature has UI): the screens/states involved, referencing scenarios. If `wireframes/` exists, link the screen files and note only what the drawing can't say (data source per field, async states); otherwise a list of states is enough. Don't design visuals here.

7. **Test hooks.** Anything design must provide so tests.md can be written without hand-waving: how to fake an external dependency, how to force an exception flow, how to observe an async outcome. Test-spec reads this section first.

## Gate

- [ ] `feedback.md` has no open items on this phase's input artifact; open items on `design.md` were addressed in this run.
- [ ] Every `Main flow` scenario in spec.md is covered by a diagram (`%% covers` line).
- [ ] Every `Exception` scenario that changes interaction is covered, or listed under "Not diagrammed" with a reason.
- [ ] Every participant in every diagram is defined under Components.
- [ ] Every endpoint, event or store operation shown in a diagram exists under Contracts (or Components for existing unchanged ones).
- [ ] Every contract names the REQ(s) it serves.
- [ ] At least one decision with a rejected alternative, or `None — <why>`.
- [ ] Risks cover partial failure and rollback.
- [ ] Test hooks cover every exception flow in spec.md (how to trigger it under test).
- [ ] No behavior appears here that isn't in spec.md — if you discovered one, it's a spec change: stop and say so.
- [ ] Every diagram parses: `python scripts/spec_lint.py docs/features/<slug>` reports no `mermaid` errors. If the lint says mermaid wasn't validated, run `npx -y @probelabs/maid docs/features/<slug>/design.md` before claiming the gate — a diagram that doesn't parse renders as an error box on the review site.
- [ ] `python scripts/spec_lint.py docs/features/<slug>` reports no errors.

Then stop. In the review message: components (new vs existing), contracts changed, decisions, and any spec gaps discovered. Ask for approval before test-spec.
