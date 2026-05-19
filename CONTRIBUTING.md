# Contributing

`pexip-infinity-skills` is the umbrella Agent Skills package for the Pexip
Infinity platform. It is a **public** repository.

> A full contribution guide arrives with the initial skill import. This file
> exists today so the hygiene policy below is committed alongside the hooks
> that enforce it.

## Hygiene policy (public repo)

Because this is public, several categories of content must never end up in
a commit. Most of this is enforced automatically by pre-commit hooks; the
categories are listed here so contributors know what to expect.

- **No author-tool attribution.** Commit messages and file content must not
  identify the editor, IDE, or any assistive tool used to author the change.
- **No local agent scratch files.** Editor- and agent-local state files,
  notes, and scratch directories are gitignored and must not be force-added.
- **No internal-only notes.** Brainstorming, design rationale, and any
  content tagged as internal or non-public stays out of this repo.
- **No secrets.** Credentials, tokens, private keys, and live config files
  are gitignored and additionally screened by a secret scanner on every
  commit and in CI.
- **No customer-identifiable data.** Email addresses are restricted to a
  short allowlist of documentation domains. IPv4 addresses are restricted
  to RFC 1918 private space, RFC 5737 documentation ranges, and loopback.

The exact patterns and allowlists live in `scripts/hygiene/` and
`.gitleaks.toml`. If a documented placeholder you need to use trips a hook,
extend the allowlist there rather than disabling the hook.

## Local setup

```bash
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

The hooks are intentionally fast — heavier checks (skill validation) run
in CI, not on commit, so the local loop stays snappy.
