# Publishing to PyPI

The CLI is published to [PyPI](https://pypi.org/project/praetorian-cli/) from GitHub
Actions using [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(OpenID Connect). No API token is stored anywhere — PyPI trusts this repository
directly, and each run gets a short-lived credential.

The workflow lives at
[`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml) and is
triggered manually.

## Cutting a release

1. **Bump the version.** Update `version` in [`setup.cfg`](../setup.cfg) and add an entry
   to [`CHANGELOG.md`](../CHANGELOG.md). Open a PR and merge it to `main`.
2. **Run the workflow.** Go to the **Actions** tab → **Publish to PyPI** → **Run
   workflow**, and run it from `main`.
3. **Approve** the deployment if the `pypi` environment has required reviewers
   (see below).

The workflow then:

- reads the version from `setup.cfg`;
- fails fast if that version is already on PyPI (bump it first);
- builds the sdist and wheel and runs `twine check`;
- publishes to PyPI via OIDC; and
- creates and pushes a `vX.Y.Z` git tag.

That's the whole release process — there is no local script to run and no credentials
to manage on your machine.

## One-time setup

These steps only need to be done once (they are already in place for the live project;
this section documents them for reference and for standing up the flow elsewhere).

### 1. Trusted Publisher on PyPI

As a maintainer of the project, go to
**[Manage project → Settings → Publishing](https://pypi.org/manage/project/praetorian-cli/settings/publishing/)**
and add a new GitHub publisher with these exact values:

| Field           | Value              |
| --------------- | ------------------ |
| Owner           | `praetorian-inc`   |
| Repository name | `praetorian-cli`   |
| Workflow name   | `publish-pypi.yml` |
| Environment name| `pypi`             |

No token is generated — this is the only credential configuration needed.

### 2. `pypi` environment on GitHub

In the repository, go to **Settings → Environments → New environment** and create one
named **`pypi`** (it must match the environment name above).

This is also where you add a **manual approval gate**: under **Required reviewers**, add
the people allowed to approve a publish. When set, every run pauses for approval before
the `publish` job pushes anything to PyPI.

## How it works

The workflow uses three jobs:

| Job       | Permission        | Purpose                                                        |
| --------- | ----------------- | ------------------------------------------------------------- |
| `build`   | `contents: read`  | Resolve/guard the version, build the sdist + wheel, `twine check`. |
| `publish` | `id-token: write` | Publish to PyPI via Trusted Publishing (OIDC). No token used.  |
| `tag`     | `contents: write` | Push the `vX.Y.Z` release tag after a successful publish.      |

All actions are pinned to commit SHAs, and each job runs with
[Harden-Runner](https://github.com/step-security/harden-runner) in audit mode, matching
the repository's supply-chain security posture.

## Notes

- The **Run workflow** button only appears once the workflow file is present on the
  default branch (`main`).
- The version guard means re-running the workflow without bumping the version is a safe
  no-op — it fails before uploading rather than producing a confusing PyPI error.
- Publishing no longer requires a PyPI API token or a `~/.pypirc` file on any developer
  machine.
