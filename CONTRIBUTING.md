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

CI must pass and a review is expected before merge.

**Server-side enforcement is not switched on, and can't be yet.** GitHub requires
Pro or Team to protect a branch on a *private* repo, and this org is on the free
plan — both the branch-protection and rulesets APIs return 403. Making the repo
public would unlock it, but `corpus/pdf/` holds several hundred third-party exam
PDFs, so that isn't an option.

So the rule is enforced two ways, neither of them airtight:

| | |
|---|---|
| `.githooks/pre-push` | refuses a push to `main`. Per-clone, opt-in, bypassable with `--no-verify` |
| CI | runs on every PR *and* every push to `main`, so a direct push still gets checked |

To close the gap properly: **GitHub Team is $4/user/month**, and then
`required_pull_request_reviews` and `enforce_admins` can be turned on for real.
Worth doing once more than two people are committing.

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
