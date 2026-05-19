# Release process

Releases are fully driven by pull requests. Adding the `release` label to a PR is the
single gesture that initiates a release: the bot prepares the version bump and changelog
automatically, and merging the PR publishes the package to PyPI via Trusted Publishing.

---

## How to release (TL;DR)

### Normal feature/fix PR that should also release

1. Open your PR as usual and get it reviewed.
2. Add the `release` label.
   - The bot commits a version bump and updated `CHANGELOG.md` to your branch.
   - The bot posts a comment confirming the new version and inviting you to edit the changelog if needed.
3. Merge the PR. PyPI publishing starts automatically after the merge.

> PRs merged **without** the `release` label are never bumped or published. Their commits
> accumulate and will be included in the next release's changelog whenever that is triggered.

### Release unreleased changes without new code

If several PRs have been merged without the `release` label and you want to cut a release
without introducing any further code changes:

1. Go to **Actions → Nuclia → Run workflow**.
2. Optionally pick a bump type (`patch` / `minor` / `major`); leave blank to auto-detect
   from conventional commit history.
3. The bot creates a `release/auto` branch, commits the version bump and changelog, opens
   a PR already labeled `release`, and posts a summary comment.
4. Review the changelog, approve, and merge. PyPI publishing starts automatically.

---

## How the release process works

The workflow lives entirely in `.github/workflows/nuclia.yml`, which is the single entry
point for all CI and release activity. Here is what happens at each stage:

### On every pull request commit (`opened`, `synchronize`, `reopened`)

1. **`check-changes`** — inspects which files changed. If no files under `nuclia/` or
   `.github/workflows/` were touched (e.g. only `CHANGELOG.md` or `VERSION` changed),
   the subsequent test jobs are skipped automatically.
2. **`test-stage`, `test-prod`, `test-windows`** — run in parallel if `check-changes`
   reports relevant changes. They delegate to the reusable workflow files `stage.yml`,
   `prod.yml`, and `windows.yml` respectively, so job definitions live in a single place.
   These jobs are also skipped when the PR comes from the `release/auto` branch (the
   release preparation commit has no code changes worth retesting).

### When the `release` label is added to a PR (`labeled`)

4. **`prepare-release-commit`** — runs immediately:
   - Generates a short-lived token via the Nuclia Service Bot GitHub App.
   - Checks out the PR branch with that token (so the subsequent push is attributed to
     the bot and can bypass branch protection).
   - Installs and runs `commitizen` (`cz bump --allow-no-commit --changelog`), which
     inspects all conventional commits since the last tag to determine the bump type
     (`fix:` → patch, `feat:` → minor, breaking change → major), updates `VERSION` and
     `CHANGELOG.md`, and creates a bump commit.
     
     > **Conventional commits matter.** If none of the commits since the last tag follow
     > the `type: description` format, commitizen falls back to a patch bump and produces
     > an empty changelog section (just the version header, no entries). To get meaningful
     > automatic release notes, use conventional commit messages: `fix: ...`, `feat: ...`, etc.
     > You can always edit `CHANGELOG.md` manually before merging.
   - Pushes the bump commit back to the PR branch.
   - Posts a PR comment confirming the new version and inviting changelog edits.
   
   Tests are intentionally **not** re-run on this event — the `labeled` trigger is
   excluded from `check-changes` and the test jobs.

### When a PR with the `release` label is merged

5. **`publish-pypi`** — runs only when `merged == true` and the `release` label is
   present, and only if no test job failed or was cancelled:
   - Generates a bot token, checks out the merge commit.
   - Creates and pushes the version tag (e.g. `v4.10.0`) on the merge commit.
   - Builds the package with `uv build`.
   - Publishes to PyPI using `pypa/gh-action-pypi-publish` via OIDC Trusted Publishing
     (no stored PyPI token).
   
6. **`publish-docs`** — runs after `publish-pypi`, syncs the `docs/` folder to S3 via
   an assumed AWS IAM role (also OIDC, no stored AWS credentials).

### Manual release via `workflow_dispatch`

The **`prepare-release`** job only runs when the workflow is triggered manually from the
Actions tab. It:
- Force-deletes any existing `release/auto` branch to avoid conflicts.
- Creates a fresh `release/auto` branch from `main`.
- Runs `cz bump` with an optional bump-type override.
- Pushes the branch and opens a PR labeled `release`.

From that point on, the PR follows the normal merge → publish flow above.

---

## PyPI security and configuration

### Trusted Publishing (OIDC)

The package is published without any stored PyPI token. Instead, GitHub requests a
short-lived OIDC JWT at workflow runtime and exchanges it with PyPI for a scoped upload
credential. This is configured on PyPI under the package's **Trusted Publishers** settings:

| Field | Value |
|---|---|
| Repository | `nuclia/nuclia.py` |
| Workflow | `nuclia.yml` |
| Environment | `pypi` |

### `pypi` GitHub Environment (approval gate)

The `publish-pypi` job runs under the `pypi` GitHub Environment (repo Settings →
Environments). This environment requires explicit approval from the `@nuclia/publishers`
team before the job proceeds. The job will pause at the environment gate even if all
tests passed and the PR was merged — a human must approve before the upload happens.

### CODEOWNERS protection

`.github/CODEOWNERS` requires a review from `@nuclia/publishers` on any PR that touches
`.github/workflows/`. This prevents someone from modifying the workflow to bypass the
`pypi` environment gate and then self-merging.

The "Require review from Code Owners" option must be enabled in the branch protection
rule for `main` for this to take effect.

### Nuclia Service Bot (GitHub App)

The bot token is used for commits and pushes that need to
bypass the branch protection "required pull request reviews" rule. The app credentials
are stored as:

- `vars.GHAPP_NUCLIA_SERVICE_BOT_ID` — the App ID
- `secrets.GHAPP_NUCLIA_SERVICE_BOT_PK` — the App private key

The bot was added to the "Allow specified actors to bypass required pull requests" list
in the `main` branch protection rule.
