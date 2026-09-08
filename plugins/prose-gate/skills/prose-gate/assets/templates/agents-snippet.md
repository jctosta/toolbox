## Prose standard

Documentation in this repository is linted with [Vale](https://vale.sh) against the
`Agentic` style, which targets the shape of generated prose. Findings at error level come
back automatically after every write, so text that trips a rule returns to you in the same
turn. The standard, stated once so you meet it before the first violation:

- **Start with the answer.** No "Great question", no "Let's dive into", no restating the
  request before addressing it.
- **Describe the system, not your own process.** "The scheduler retries three times", not
  "I've implemented a retry loop".
- **End at the last useful sentence.** No "Hope this helps", no "Let me know if".
- **Say what a thing does instead of praising it.** Not "robust", "seamless", "powerful",
  "comprehensive", "leverage" or "crucial".
- **Make the positive claim on its own.** Not "it isn't just a cache, it's a session
  store" — say what it is.
- **Questions as headings are padding.** Write the statement the question was leading to.
- **No emoji in prose or headings.**
- **Leave no placeholders.** No `TODO`, no `TBD`, no lorem ipsum in a document presented
  as finished.
- **Prefer the short form.** "to" over "in order to", "before" over "prior to".
- **State the claim or delete the sentence.** No "it's worth noting", no "keep in mind".

Run it yourself at any point:

```
vale --minAlertLevel=error <file>
```

The commit hook checks the same rules against **staged content**, so a fix has to be
staged to count. Fixing the file and committing without re-adding it leaves the flagged
text in the index, and the commit is refused again.

**When a rule fires on prose that is correct as written**, do not rewrite the text to
satisfy it. Suppress that passage and leave the reason visible:

```
<!-- vale Agentic.Marketing = NO -->
The vendor's product name is Seamless.
<!-- vale Agentic.Marketing = YES -->
```

That case is normal — a document naming a banned term in order to prohibit it, or a
domain word that happens to read as marketing. Rewriting accurate prose to satisfy a
pattern makes the documentation worse, which is the opposite of the point.
