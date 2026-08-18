# Contributing

Different people own different pipeline steps, so the rules exist to stop one
step's change from silently breaking the next.

## Setup

```bash
git config core.hooksPath .githooks
```

One command, once per clone. It installs the pre-push hook that stops an
accidental push to `main`.

## No direct pushes to main

Branch, push the branch, open a PR:

```bash
git switch -c 2-classify/strip-devanagari
git push -u origin 2-classify/strip-devanagari
gh pr create
```

Name the branch after the step you're working on — `1-extract/…`,
`2-classify/…`, `4-dedupe/…`. It makes it obvious who should review.

**`main` is protected server-side** by the `protect-main` ruleset. It applies to
everyone — the bypass list is empty, so admins get no exemption either.

| Rule | Effect |
|---|---|
| Pull request required | 1 approval, and **you cannot approve your own** |
| Status check `checks` | CI must pass, and your branch must be up to date with `main` |
| Squash only | one commit per PR on `main` |
| Linear history | no merge commits |
| No force push, no deletion | `main` can't be rewritten or removed |

`.githooks/pre-push` is still worth installing. It catches a push to `main` before
you wait on a network round trip, and the error tells you the branch-and-PR flow.
It's a convenience now, not the enforcement.

**You need someone else to approve.** With three people on different steps that's
the point — but it does mean a one-line fix waits for a reviewer. Ask in chat
rather than sitting on it.

## Review

Every PR gets an automated first pass and a human approval.

**Claude** reviews on open and on each push, via
`.github/workflows/claude-review.yml`. It runs on a Claude Max subscription
rather than API credits, so it costs nothing beyond quota — roughly 0.1–0.2% of
the weekly Opus budget per review, about 1–2% at ten PRs a week.

One-time setup, by whoever's subscription it runs on. **Both steps are
required** — the token alone gives `401 Claude Code is not installed on this
repository`:

1. Install the Claude GitHub App: https://github.com/apps/claude
2. Generate and store the token:

```bash
claude setup-token                      # prints a long-lived token
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo OnelyStop/question-bank
```

The prompt in that workflow carries the rules Claude can't infer from the code — no fuzzy matching in dedupe, `corpus/` is never modified in place,
answers must be a key that exists in that question's options, and each step's
output must stay a superset of the previous step's. Every one of those came from
something that actually went wrong here, so **update the config when you learn a
new rule** — that's what makes it improve.

Drafts are skipped, so iterate in draft and mark ready when you want the review.

It's a first pass, not the approval. A human still has to approve.

## What CI checks

Everything below runs on every PR. All of it runs locally too — do that first,
it's faster than waiting.

| Check | Run it yourself |
|---|---|
| Every `.py` file parses | `for f in $(git ls-files '*.py'); do python3 -m py_compile $f; done` |
| `schema.json` is a valid schema | see `.github/workflows/ci.yml` |
| Step examples match the schema | `python3 pipeline/5-validate/check_examples.py` |
| No secrets committed | `git grep -nIE 'service_role\|postgres://[^ ]*:[^ @]+@'` |
| No links to missing files | see `.github/workflows/ci.yml` |
| No paths from the old layout | `git grep -nIE 'India/banking\|papers-deduped\|feature_tables'` |
| The export validates, if committed | `python3 pipeline/5-validate/check_schema.py` |

The two worth understanding:

**Step examples match the schema.** Each step folder has an `output.json` — the
shape that step must produce, in schema field names. CI checks every field exists
in `schema.json`, has the right type, and that each step is a **superset** of the
one before it. A step that drops a field breaks everything downstream, and this
is what catches it.

**No paths from the old layout.** `India/banking/`, `papers-deduped/`,
`feature_tables/` and `pipeline/pdf|patterns/` are gone. References to them
survived four separate reorganisations in this repo and twice caused silent
breakage — a script resolving to a directory that no longer exists and returning
zero results instead of erroring. Hence a hard check.

## Changing the schema

`schema/schema.json` is the contract between this repo and the app. If you change
it:

1. Update every affected `output.json`, or CI fails.
2. Say in the PR what the app has to change. Adding an optional field is safe;
   renaming or removing one is not.
3. Update the field table in `schema/README.md`, including the `x-fill` number if
   coverage moved.

## Data

`corpus/` is input, `data/` is output. Never edit `data/` by hand — it's
generated and gitignored.

Deleting anything from `corpus/` deserves a second look: the source PDFs were
never committed, so extracted JSON in there may be the only copy of something.
Check git history before assuming a folder is reproducible.

## Commits

Say what changed and why. If a number is the reason for a decision, put the
number in the message — "37% of near-duplicate pairs differ only in their
numbers, so exact matching only" is worth more later than "improve dedup".
