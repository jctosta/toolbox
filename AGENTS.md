# Working in this repository

## Gates

```shell
python3 tests/run_checks.py --strict
vale --minAlertLevel=error .
uvx ruff check .
```

CI runs all three. For the prose gate at the commit boundary:

```shell
cp plugins/prose-gate/skills/prose-gate/assets/templates/pre-commit .git/hooks/
chmod +x .git/hooks/pre-commit
```

## Writing standard

Vale catches phrase shapes: preamble, self-narration, marketing adjectives, hedging,
rhetorical headings, sign-offs. It cannot catch unnecessary content, so:

- Say what a thing does. Give a reason only where it is not recoverable from the code,
  and then in one sentence.
- Assume a technical reader. Do not restate the previous line in other words.
- `CHANGELOG.md` entries are one line each.
- Templates and examples carry no explanatory captions.
- End at the last useful sentence.

The exception is `references/` and `SKILL.md`, which are instructions an agent follows.
A reason there changes what the agent does, so it earns its space.

When a rule fires on text that is correct as written, suppress the passage rather than
rewriting it:

```
<!-- vale Agentic.Marketing = NO -->
...the line that is correct...
<!-- vale Agentic.Marketing = YES -->
```
