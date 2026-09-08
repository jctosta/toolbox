# Plugin catalog

The lookup table for `propose`. Grouped by what a repo contains, with a starting recommendation for each. Tiers are defined in `choosing-checks.md`.

> **This list drifts.** Compiled against **qlty 0.643.0 (2026-09-03)**; qlty adds plugins and changes defaults between releases. Confirm against the installed CLI before relying on a name:
>
> ```
> qlty plugins list
> ```
>
> Two things about that command: it requires an already-initialised repository (it errors with "Qlty must be set up in this repository" otherwise), so during `propose` — which runs before `apply` — use `qlty init --dry-run` instead to see what qlty itself would pick. And some plugins are **per-language variants** rather than the single name listed here: `radarlint` ships as `radarlint-python`, `radarlint-java` and so on.
>
> If a name here is not in the CLI's output, the CLI is authoritative. If the CLI has plugins this file does not, consider them — absence here is not a recommendation against.

Recommendations mean:

- **on** — enable at adoption unless there is a reason not to
- **consider** — good candidate, but the answer depends on the repo
- **later** — real value, but not while adopting; revisit once the gate is holding
- **off** — usually more noise than signal; enable only for a stated need

---

## Any repository

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `gitleaks` | security | Committed secrets, scanning history | **on** |
| `trufflehog` | security | Secrets, with verification against live services | **on** |
| `osv-scanner` | security | Known CVEs in dependencies, across ecosystems | **on** |
| `trivy` | security | CVEs in dependencies, containers and IaC | consider — overlaps `osv-scanner`; pick one unless you ship containers |
| `semgrep` | security | Code patterns; breadth depends entirely on ruleset | consider — start in `monitor`, it is the noisiest option here |
| `editorconfig-checker` | formatter | Whitespace and line endings against `.editorconfig` | on, if the repo has an `.editorconfig` |
| `ripgrep` | linter | Custom regex checks you define yourself | later — useful for house rules once the basics hold |
| `vale` | linter | Prose style in docs | off, unless docs are a product surface |
| `dotenv-linter` | linter | Malformed `.env` files | consider, if the repo ships them |

## CI and infrastructure

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `actionlint` | linter | Broken GitHub Actions workflows, before they run | **on**, if `.github/workflows/` exists |
| `zizmor` | security | Insecure GitHub Actions patterns (injection, over-broad tokens) | on, alongside `actionlint` |
| `checkov` | security | Misconfigured Terraform, CloudFormation, Kubernetes, Docker | **on**, if the repo has IaC |
| `tflint` | linter | Terraform errors and provider misuse | on, with Terraform |
| `terraform` | formatter | `terraform fmt` | on, with Terraform |
| `kube-linter` | security | Kubernetes manifest misconfiguration | on, with k8s manifests |
| `hadolint` | linter | Dockerfile mistakes | on, with a Dockerfile |
| `dockerfmt` | formatter | Dockerfile formatting | consider |
| `yamllint` | linter | YAML syntax and style | consider — set a relaxed config first, defaults are opinionated |

## Python

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `ruff` | linter + formatter | Fast, replaces flake8, isort, pyupgrade and more | **on** — adopt `pyproject.toml`/`ruff.toml` if present. `qlty init` enables it as `drivers = ["lint"]`; add the format driver deliberately, and not alongside `black`. |
| `black` | formatter | Formatting | on, unless `ruff format` is already used — not both |
| `flake8` | linter | Classic linting | off if `ruff` is on; they overlap heavily |
| `mypy` | type-checker | Type errors | consider — on a codebase with no annotations this is a project, not a check. Start `monitor`. |
| `bandit` | security | Injection, unsafe deserialization, weak crypto | **on** |
| `pyright` / `basedpyright` | type-checker | Type errors | **not a qlty plugin** — qlty ships neither. If the repo configures one (`[tool.pyright]`, `[tool.basedpyright]`, `pyrightconfig.json`), leave it outside qlty and record that in the policy. Do not enable `mypy` as a substitute: two typecheckers on one codebase is worse than one. |

## JavaScript and TypeScript

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `eslint` | linter | The ecosystem standard | **on** — adopt the repo's config; do not shadow it |
| `oxc` | linter | Much faster subset of eslint rules | consider — as a fast pre-commit pass alongside eslint in CI |
| `biome` | formatter + linter | Combined format and lint | on **instead of** prettier + eslint, never alongside |
| `prettier` | formatter | Formatting | on, unless `biome` is |
| `knip` | linter | Unused files, exports and dependencies | later — high value, but noisy mid-migration |
| `stylelint` | linter | CSS and SCSS | on, if there is meaningful stylesheet code |

## Go

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `gofmt` | formatter | Canonical formatting | **on** — non-negotiable in Go |
| `golangci-lint` | linter | Aggregates dozens of Go linters | **on** — adopt `.golangci.yml` if present |

## Ruby

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `rubocop` | linter + formatter | The ecosystem standard | **on** — adopt `.rubocop.yml`; the team's tuning matters here |
| `standardrb` | linter | Opinionated rubocop preset | on **instead of** `rubocop`, never both |
| `brakeman` | security | Rails vulnerabilities | **on**, for a Rails app |
| `reek` | linter | Ruby-specific code smells | later — overlaps qlty's own smell checks |
| `haml-lint` | linter | HAML templates | on, if the repo uses HAML |

## Rust

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `rustfmt` | formatter | Canonical formatting | **on** |
| `clippy` | linter | Idiom and correctness lints | **on** |

## Java, Kotlin, Scala

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `google-java-format` | formatter | Formatting | on, if the team accepts the style |
| `checkstyle` | linter | Style and some correctness | consider — adopt the existing `checkstyle.xml` |
| `pmd` | linter | Bug patterns and complexity | consider — overlaps qlty's smells |
| `ktlint` | formatter + linter | Kotlin | **on**, for Kotlin |
| `radarlint-*` | linter | Sonar-derived rules, one plugin per language (`radarlint-python`, `radarlint-java`, …) | consider — closest thing to what SonarQube reported, and what `qlty init` picks by default |

## PHP

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `php-cs-fixer` | formatter | Formatting | **on** |
| `php-codesniffer` | linter | Standards compliance | consider — overlaps `php-cs-fixer` |
| `phpstan` | type-checker | Static analysis by level | **on** — start at a low level and raise it |

## Swift, C/C++, C#, others

| Plugin | Tier | Catches | Start |
|---|---|---|---|
| `swiftformat` | formatter | Formatting | **on**, for Swift |
| `swiftlint` | linter | Style and correctness | **on**, for Swift |
| `stringslint` | linter | Unused and missing localized strings | consider, for a shipped app |
| `coffeelint` | linter | CoffeeScript | on, only if the repo still has it |
| `sqlfluff` | linter | SQL style and parse errors | consider, if SQL is checked in |
| `prisma` | linter | Prisma schemas | on, with Prisma |
| `spectral` | linter | OpenAPI and AsyncAPI specs | on, if an API spec is checked in |
| `redocly` | linter | OpenAPI | on **instead of** `spectral` |
| `markdownlint` | linter | Markdown structure | consider — off unless docs are a product surface |
| `shellcheck` | linter | Shell script bugs | **on**, wherever there are shell scripts. Very high signal. |
| `shfmt` | formatter | Shell formatting | on, alongside `shellcheck` |
| `ast-grep` | linter | Structural custom rules | later — for house rules, once the basics hold |

## Pairs that should not both be on

Enabling both halves of any of these produces duplicate findings and contradictory fixes:

- `biome` and (`prettier` + `eslint`)
- `ruff` and `flake8`
- `black` and `ruff format`
- `rubocop` and `standardrb`
- `spectral` and `redocly`
- `osv-scanner` and `trivy`, for dependency CVEs specifically — `trivy` earns its place when you also scan container images
