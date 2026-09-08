# Phase: explore

Produces `docs/features/<slug>/brief.md`. The brief answers *why this, why now, which shape, what's out*. It deliberately does not answer *what exactly the system does* — that's refine — and it forbids solution design before options are on the table.

## Inputs

- The idea, ticket, or issue. If it's an external ticket, fetch it (GitHub/ClickUp) and quote the original words in the brief — paraphrase loses nuance.
- `docs/product/product.md` and `domain.md` — read both. Use the glossary vocabulary. Identify which capability this belongs to.
- Existing features in `docs/features/` that touch the same capability — list them under Related.

If `docs/product/` doesn't exist, stop and offer define-app first. A brief without product context produces features that don't fit.

## Method

1. **Restate the problem** in one sentence from the actor's point of view, without mentioning any solution. If you can't, you don't understand the problem yet — ask.
2. **List at least two options** for the shape of the solution. Not implementation choices (that's design) — product-level shapes. "A reminder per task vs. a daily digest vs. an in-app badge" is options; "Postgres vs. SQLite" is not. For each option: one line of what it is, one line of the main trade-off. Include the option of doing nothing or doing less if it's credible.
3. **Pick a direction** and say why, referring to the trade-offs. If the user must pick, present the options and stop — don't pick for them on a decision that changes product shape.
4. **Draw the scope boundary**: in scope as a short list of capabilities the feature delivers; out of scope as a list of things a reader would reasonably assume are included but aren't, each with "→ future" or "→ never" and a reason.
5. **Identify actors and touched entities** from product.md/domain.md. If the feature needs a new entity or a new lifecycle state, say so here — refine will need domain.md updated first.
6. **Collect open questions**, each with an ID `Q-NN`, an owner (user / reporter / agent-can-investigate) and a `blocking` or `non-blocking` tag. Blocking means refine cannot proceed without the answer.
7. **Set the rigor level** (lite/full) using the criteria in SKILL.md and justify it in one line. Anything touching personal data, money, health, external contracts or migrations is full.

## Interview

Ask up to 5 questions, one round, before writing. Prefer questions that eliminate an option over questions that add detail. Good: "Does a reminder go to everyone on the list, or only the task owner?" Bad: "What color should the button be?"

Anything not asked and not answered gets written as `(assumed)` or as an open question — never silently decided.

## Writing brief.md

Use `assets/templates/brief.md`. Keep it to one screen. A brief that needs scrolling is doing refine's job.

## Gate

- [ ] `feedback.md` has no open items on this phase's input artifact; open items on `brief.md` were addressed in this run.
- [ ] Problem statement mentions an actor and an outcome, and no solution.
- [ ] At least two options listed, each with a trade-off; the chosen one references the trade-offs.
- [ ] Out of scope has at least one entry with a reason.
- [ ] Capability field matches an entry in product.md's capability map.
- [ ] Every actor named exists in product.md; every entity named exists in domain.md, or is flagged as new under "Domain changes".
- [ ] Every open question has an ID, an owner and a blocking tag.
- [ ] No blocking question is unanswered — or the brief is explicitly marked `status: blocked` with the Q-IDs.
- [ ] Rigor level is set and justified.
- [ ] Original ticket text is quoted verbatim if there was a ticket.
- [ ] `python scripts/spec_lint.py docs/features/<slug>` reports no errors for brief.md.

Then stop. Summarize: the problem, the chosen direction, what's out, blocking questions (if any), assumptions. Ask for approval of the brief before refine.
