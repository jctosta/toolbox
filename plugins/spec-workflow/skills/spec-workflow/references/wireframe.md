# Phase: wireframe

Produces `docs/features/<slug>/wireframes/*.html`: one hand-drawn-looking screen per UI-bearing main flow, so the human can see what the feature looks like before design.md commits to how it works. Optional — a feature without UI, or one whose screens already exist, skips it. Skipping is recorded nowhere: no `wireframes/` folder means the phase wasn't run.

Run it after `refine` and before `design`. The screens are deliberately ugly: grayscale, sketchy strokes, crossed boxes instead of imagery. Anything that invites a conversation about brand, colour or spacing is a bug in the wireframe.

## Inputs

- `spec.md` — must exist and be approved. If it isn't, stop and point at the pending `refine` (or the review that hasn't happened yet).
<!-- vale Agentic.Placeholder = NO -->
- `docs/product/domain.md` — every label, state name and message on a screen uses this vocabulary verbatim. Never lorem ipsum, never invented synonyms.
<!-- vale Agentic.Placeholder = YES -->
- Existing `wireframes/` for this feature (a second run edits screens, it doesn't start over) and for neighbouring features under the same capability, so screens of one product look like one product.
- `feedback.md` — open items on `spec.md` block this phase; open items on a screen are addressed in this run.

## Method

1. **Pick the UI-bearing scenarios.** Walk every `Main flow` in spec.md and decide whether an actor sees something. A scheduled job, an audit record or a system-to-system effect is not UI. Keep the list of the ones you ruled out with a one-line reason each — it goes in the review message, and if the answer is "no UI at all", say so and produce no folder.

2. **One screen per UI-bearing main flow.** Kebab-case file name after what the actor is doing (`due-date-form.html`, `delivery-status.html`), not after the requirement number. Two main flows that are the same screen in different states are one file.

3. **States for alternatives and exceptions.** A rejected duplicate, an empty list, a failed delivery — show them as visible `.state` blocks on the screen they belong to, or as a separate `<screen>--<state>.html` when the whole layout differs. Pick whichever reads clearer at a glance; both count for coverage.

4. **Declare coverage on the first line.** Every file starts with `<!-- covers S-01.1, S-01.2 -->` before the doctype. A main flow the lint expects but that genuinely has no screen gets `<!-- no-ui: S-03.1 the scheduler runs unattended -->` in any file of the folder.

5. **Write the copy from the spec.** Field labels, button text, error text and confirmations are the THEN lines of the scenario, said the way a screen says them. If you need a word the spec doesn't have, that is a spec gap — flag it in the review message rather than inventing product copy.

6. **Link the flow.** Screens of the same flow reach each other with plain relative `<a href="other-screen.html">`. No router, no JS navigation.

7. **Stay lo-fi.** `assets/templates/wireframe.html` is the skeleton; copy it. The look comes from wired-elements (CDN ESM import) plus `docs/features/.wireframe.css` — copy `assets/templates/wireframe.css` there on the first run of the phase in a repo. No framework, no build step, no local assets: a screen must render from the folder alone, wherever it's copied (X-01). No colour beyond the grayscale the stylesheet defines (X-02), no logos, no photos — `<div class="placeholder">` is what an image looks like here.

8. **Keep it readable offline.** Labels, button text and links live in the light DOM so the screen still reads when the CDN can't be reached; the stylesheet's `:not(:defined)` rules draw the boxes. Never build content in JavaScript.

## Gate

- [ ] `spec.md` exists and is approved; `feedback.md` has no open items on it.
- [ ] Every `Main flow` scenario is either covered by a screen or has a `no-ui:` line with a reason.
- [ ] Every file's first line is a `covers` comment naming scenarios that exist in spec.md.
- [ ] Every alternative and exception flow of a covered requirement appears as a state block or its own file.
- [ ] Every internal link resolves to a file that exists in the folder.
<!-- vale Agentic.Placeholder = NO -->
- [ ] Copy uses domain.md vocabulary; no lorem ipsum, no colour, no brand, no real imagery.
<!-- vale Agentic.Placeholder = YES -->
- [ ] Nothing on a screen implies behavior that isn't in spec.md — if you drew one, it's a spec change: stop and say so.
- [ ] `python scripts/spec_lint.py docs/features/<slug>` reports no errors.

Then stop. In the review message: the screens produced with the scenarios each covers, the main flows judged non-UI with their one-line reason, any spec gap the drawing exposed, and `spec-workflow:site` as the way to look at them. Don't start `design`.
