# Phase: assess

Produce an accurate picture of what prose this repository holds and what already governs it, so `propose` argues from facts rather than from file extensions. This phase decides nothing.

## Inputs

The repository. Optionally free text about what prompted this ("our docs read like an AI wrote them", "we keep shipping TODO placeholders", "a reviewer complained about the README").

## Method

1. Run the detector and read it carefully:

   ```
   python scripts/vale_advisor.py detect <path>
   ```

   It reports prose files by count and line total, source files whose comments Vale would read, existing prose tooling, whether `vale` and `vale-ls` are installed, and any `.vale.ini` already present.

2. Check the tool:

   ```
   vale --version
   ```

   Missing it is normal. Offer `brew install vale` (or the release tarball on Linux) and carry on; `assess` and `propose` need no binary. `vale-ls` is a separate download from its releases page and its absence is expected.

3. **Separate prose from things that only look like prose.** The detector counts files; you decide which of them anyone actually writes:

   - **Generated documentation** — API references built from source, changelogs assembled by a release tool. Linting these fires on text no human controls.
   - **Vendored and third-party docs** — a license, a copied RFC, an upstream README.
   - **Fixtures** — sample text that exists to be wrong. A prose-linting repo will have some, and they must be excluded or the gate reports its own test data.
   - **Templates with placeholders** — a scaffold full of `<PLACEHOLDER>` trips `Placeholder` by design.

   Each of these becomes an exclusion in `propose`, and finding them now is cheaper than triaging them later.

4. **Find the house conventions the style would fight.** This is the highest-value step in the phase, and skipping it is how a gate arrives with dozens of failures on correct text. Look for notation the repo uses deliberately:

   - Arrow characters, mathematical symbols or box drawing used as punctuation
   - Domain terms that read as marketing (a product genuinely called "Seamless")
   - Words a rule bans that this project uses precisely
   - Documents that *name* a banned term in order to prohibit it, which is not the same as using it

   Record each one with the rule it would trip. `propose` decides what to do about it.

5. **Establish who writes here.** Prose written mostly by agents needs the error tier and the hook. Prose written mostly by hand, reviewed by people who care, may need far less. Ask rather than assume.

6. **Measure, if `vale` is installed.** A count now is the argument `propose` will use:

   ```
   vale --no-exit --output=JSON --minAlertLevel=suggestion <paths>
   ```

   Total, by severity, and by rule. Do not tune anything yet; just record it.

7. Write the **Prose profile** section of `docs/quality/prose-policy.md` (copy `assets/templates/policy.md` if the file does not exist). Set `status: assessed`.

## Gate

- [ ] Prose files listed by count and line total, with generated, vendored, fixture and template files separated out
- [ ] Source files whose comments would be linted are identified, or ruled out
- [ ] Existing prose tooling named with its config file, and whether CI runs it
- [ ] House conventions that would trip a rule are listed, each with the rule it trips
- [ ] Who writes the prose here is recorded, from an answer rather than an assumption
- [ ] A measured count exists, or the reason it does not (`vale` absent) is stated
- [ ] `status: assessed`, `updated` set

Then stop. Summarize: what prose this repo holds, what governs it today, who writes it, and the one convention most likely to fight the ruleset.
