# Choosing rules that are worth running

Read this during `propose`, and again during `apply` when deciding what to do about a finding.

The failure this file exists to prevent: switching on a style, producing three hundred findings, and watching everyone learn that the prose gate is something you route around. Every rule you enable spends a little of the team's attention.

## Start from what is wrong with the prose

Work backwards from the complaint, not forwards from the rule list.

| What is going wrong | What actually helps |
|---|---|
| "The docs read like an AI wrote them" | `Preamble`, `Narration`, `Signoff`, `NotXButY`, `Rhetorical` |
| Adjectives instead of behaviour | `Marketing` |
| Placeholders shipped to users | `Placeholder` |
| Padding nobody reads | `Hedging`, `Wordiness` |
| Sentences readers have to re-read | `SentenceLength`, `ParagraphLength` |
| Emoji in a serious reference | `Emoji` |
| Copy-paste doubling | `Repetition` |
| Nothing in particular | `Placeholder` and `Repetition`. Stop there for a month. |

A rule that does not map to something someone has actually complained about is a candidate for off, not for error.

## The tiers

Ordered by how often a hit is genuinely wrong. This is the ordering that decides levels.

### 1. Mechanical — a hit is always a defect

`Repetition` ("the the"), `Placeholder` (`TODO`, `TBD`, lorem ipsum), `Emoji` where the house style bans them.

No judgment involved and near-zero false positives. These belong at `error` from day one. They are also the rules that justify a gate to a sceptic, because nobody argues that shipping `TODO` in a published document was intentional.

The one failure mode is **mention versus use**: a document that says "never write TODO" trips `Placeholder` legitimately. Suppress inline at that line; do not weaken the rule and do not add the term to the vocabulary, which would exempt it everywhere and defeat the point.

### 2. Agent tells — a hit is usually a defect

`Preamble`, `Narration`, `Signoff`, `NotXButY`, `Rhetorical`, `Marketing`.

These target the shape of generated prose, and they are the reason this style exists. A human writer trips them occasionally; a model trips them constantly. `error` is defensible for a repo whose docs are largely agent-written, and `warning` is the right start where people write most of the prose.

Two carry known weaknesses worth knowing before you set a level:

- **`Rhetorical` cannot tell a rhetorical throat-clear from a real question.** "Why does this matter?" as a heading is padding. The same words as a cell in a question-and-answer table are the point of the table. The shipped rule is scoped to headings for exactly this reason; unscoped it fires on ordinary prose and tables.
- **`Marketing` fires on domain vocabulary.** A product genuinely named "Seamless", or a database that really is distributed, will trip it. That is what the vocabulary is for.

### 3. Style preferences — a hit is an opinion

`Hedging`, `Wordiness`, `SentenceLength`, `ParagraphLength`.

Often right, sometimes wrong, and always arguable. `warning`. Promoting these to `error` produces exactly the gate people learn to bypass, and the bypass habit then covers tier 1 as well.

`SentenceLength` at 30 words deserves a mention: it is the one rule in this tier where the findings are mostly real, and a measured pass through them usually improves the prose. Worth doing once, deliberately, rather than gating on.

### 4. Whole-document metrics — a hit is a hint

`Readability` (Flesch-Kincaid grade).

`suggestion`, or off. Grade level measures sentence and word length, which is a poor proxy for whether a reference document is clear to the engineers reading it. Precise technical writing scores badly and is correct. Never gate on it.

### The one that needs its own paragraph

**`Passive`** is a regex for `be` plus a past participle, not a parser. It cannot distinguish an agentless passive that hides a real actor ("the tokens are validated", by what?) from one where the actor is genuinely irrelevant ("the config is read at startup"). In technical prose the second is common and correct.

On a real corpus it is routinely the single largest source of findings — measured at 208 of 293 on one repository, or seventy percent of everything the style reported. That is the definition of a rule that has not earned its noise. Keep it at `warning` so a writer looking for it can find it, and do not gate on it. Rewriting correct agentless passives to satisfy a regex makes documentation worse.

## Levels, and what they mean

| Level | Meaning | Use for |
|---|---|---|
| `error` | Blocks. A hit is always wrong. | Tier 1, and tier 2 on agent-written repos |
| `warning` | Reports. A competent writer might defend it. | Tier 2 and 3 |
| `suggestion` | Advisory. | Tier 4 |

`MinAlertLevel` in `.vale.ini` sets what Vale *prints*. What *blocks* is `--minAlertLevel` passed by each surface. Keeping the file at `warning` and the gate at `error` gives a human running `vale .` the full picture while only mechanical defects fail a build.

## What not to gate on

- **Readability grade.** Measures the wrong thing for reference documentation.
- **Total finding count on an existing corpus.** It reflects how long the docs have existed. Gate the error tier and let the rest be visible.
- **`Passive`.** See above.
- **Anything currently at `warning`.** A rule not trusted enough to block is not trusted enough to be reported as a failure.

## When a rule fires on correct prose

This is the decision `apply` makes repeatedly, in order of preference:

1. **Fix the rule** when its pattern is wider than its own description. This helps every repository, not just this one. The shipped `Emoji` rule originally matched the whole range from `2190` to `27BF`, which covers arrows, mathematical operators and box drawing — so `→` used as punctuation read as an emoji. Narrowing the range was correct; exempting the arrow would have left the bug in place for everyone else.
2. **Scope the rule** with `scope: heading` or a path section, when it is right generally and wrong in one place.
3. **Suppress inline** with a `<!-- vale Rule = NO -->` pair, when a passage names a banned term deliberately. Self-documenting, and local.
4. **Add to the vocabulary**, for project nouns only.
5. **Turn it off**, with the reason recorded.

Rewriting accurate prose to satisfy a pattern is not on this list. A linter that makes documentation worse has negative value, and this is the judgment the whole plugin turns on.

## Beyond the shipped style

Vale has an ecosystem of packages installed via `vale sync`: house styles from large documentation teams, `write-good` and `proselint` for general English, `alex` for inclusive language, and spelling. They cover different ground from `Agentic`, which targets generated prose specifically.

Adopting one alongside is reasonable, and adopting one at `error` on an existing corpus is not. Bring it in at `suggestion`, read what it says about the repo for a week, then decide. The counts will be much larger than this style's.
