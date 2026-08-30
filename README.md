# larkbatis.github.io

The LarkBatis documentation site: [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/),
versioned with [mike](https://github.com/jimporter/mike), published to GitHub
Pages at <https://larkbatis.github.io/>.

This repository holds **only** the site. The code lives in
[`larkbatis/`](https://github.com/larkbatis/larkbatis),
[`larkbatis-spring/`](https://github.com/larkbatis/larkbatis-spring) and the
two build-plugin repos.

## What is in here

```
docs/                  the site content — English only
  index.md
  getting-started/     quick start, Spring Boot, build plugins, JPMS
  usage/               mappers, XML, dynamic SQL, foreach, result maps,
                       generated keys, streaming, transactions, raw SQL,
                       types, Spring, troubleshooting
  wiki/                architecture, shape vs value, generated code,
                       life of a call, design red lines, performance
  features/            MyBatis differences, annotations, runtime API,
                       configuration, errors, migration, roadmap
  stylesheets/
overrides/main.html    theme override
mkdocs.yml             site config and nav
requirements-docs.txt  pinned mkdocs-material + mike
.github/workflows/docs.yml
```

**English only.** The Vietnamese design artifacts in the workspace's `docs/`
folder are an *input* to these pages, never a page of them.

## Running it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-docs.txt

mkdocs serve            # live reload on http://127.0.0.1:8000
mkdocs build --strict   # what CI runs — a broken link or a nav entry pointing
                        # at a missing file fails here
```

`site/` and `.venv/` are git-ignored.

Dependencies are pinned so a docs build is reproducible and a Material release
never breaks CI unattended. Bump them deliberately, then re-run the strict
build.

## How publishing works

Two jobs, on purpose.

```
push to main / release published / workflow_dispatch
        │
   ┌────▼─────────────────────────────────────────────┐
   │ version   mkdocs build --strict   (nothing committed yet)
   │           mike deploy --push --update-aliases <ver> [aliases]
   │           → commits ONE version into the gh-pages branch
   └────┬─────────────────────────────────────────────┘
        │  gh-pages is a *content store*, not a served site:
        │  it accumulates 0.1/, 0.2/, dev/, latest/, versions.json
   ┌────▼─────────────────────────────────────────────┐
   │ publish   checks that branch out and hands it to
   │           GitHub Pages as an artifact
   └──────────────────────────────────────────────────┘
```

Pages' "source" is therefore **GitHub Actions**, not a branch.

Splitting the jobs keeps `contents: write` (which mike's commit needs) away
from the job holding `id-token: write`, and makes the two failure modes
distinct: a broken doc build never touches the live site, and a Pages outage
never loses a built version.

### Which version gets deployed

| Trigger | Version | Aliases |
|---|---|---|
| push to `main` | `dev` — the moving development site | none |
| release published | tag `v0.1.0` → `0.1` (mike's recommended granularity) | `latest` |
| `workflow_dispatch` | whatever you type | whatever you type |

`mike set-default --push --allow-undefined latest` runs every time; it is
idempotent, and `--allow-undefined` keeps the very first dev-only deploy from
failing before any release has claimed the alias.

Two details in that workflow are deliberate and easy to break by tidying:
`fetch-depth: 0`, because mike reads and rewrites `origin/gh-pages` and a
shallow checkout fails on the first deploy of a second version; and release
event data passed through `env:` rather than interpolated into a script body,
because a tag name is attacker-influenceable text.

mike pushes to `gh-pages` with `GITHUB_TOKEN`, and pushes made with that token
do not trigger workflows — so this file cannot retrigger itself.

## Editing

The header repo icon points at the **code** repo; the per-page edit button
points back into this one, via an explicit `edit_uri_template` (the default
`edit_uri` is resolved against `repo_url`).

There is no remote configured on the local checkout — pushing is done by hand.

## Adding a page

1. Write the Markdown under the right section of `docs/`.
2. Add it to `nav:` in `mkdocs.yml` — `--strict` fails on an orphan or a
   dangling nav entry.
3. `mkdocs build --strict` locally before pushing.
