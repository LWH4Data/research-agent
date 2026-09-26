# Research Agent development

This is the development checkout. Product operation rules live in
[resources/AGENTS.runtime.md](resources/AGENTS.runtime.md); read them before
changing behavior or operating the library. The personal skill and registered
agents load that canonical product file, not this development guide. Runtime
restrictions on generated library data do not prohibit authorized source-code,
test, or documentation changes in this checkout.

## Start with the relevant context

- Confirm the repository root and working tree before editing. Start new Codex
  development tasks in this checkout so its project instructions are discovered;
  when working from another directory, read this file explicitly and use this
  repository as the working directory for commands.
- Use [docs/technical/README.md](docs/technical/README.md) as the topic index.
  Read the affected topic in one language, then its linked implementation and
  tests; do not load both translations or every technical document by default.
- [ROADMAP.md](docs/technical/ko/ROADMAP.md) owns current status, next work, and
  completion criteria. Technical topic files describe current behavior and why;
  `docs/technical/ko/experiments/` and `docs/technical/en/experiments/` contain
  dated evidence and reproduction steps in the corresponding language.
  Update the existing roadmap for substantial unfinished work instead of
  starting a second competing plan. Record unresolved limits when handing off.
- Before resuming or proposing the next task, read the roadmap's
  [current-work checkpoint](docs/technical/ko/ROADMAP.md#current-work) and the
  user's latest agreement. Continue from the recorded step; do not infer a new
  priority from an incomplete milestone. Update that checkpoint with completed
  work, the next concrete action, and missing user-provided material at handoff.
- This root `.codex/config.toml` is development-only. The release maps
  `resources/codex.runtime.toml` to `.codex/config.toml`; preserve that boundary.

## Boundaries

- Keep configured original sources and user attachments read-only. Never use a
  user's original folder as test output or broaden its write permissions.
- Preserve existing and concurrent edits; inspect the diff before changing files.
- Use disposable stores, source fixtures, HOME, and Trash for installation,
  registration, migration, and removal tests. Do not uninstall a real installation
  or run subscription model calls against user data merely to test a change;
  those operations require authorization for that actual use.
- Preserve model routing (Luna xhigh management, Sol high visual review) and
  launcher/permission boundaries unless the user explicitly requests a change.

## Change-impact review

Before finishing, check the affected responsibilities rather than only the file
that was edited:

- CLI or data changes: schema/version compatibility, atomic writes and recovery,
  concurrent operations, source protection, and relevant tests.
- Skill or agent changes: canonical product rules, source templates, generated
  personal registrations, launcher paths, and whether existing installations
  need re-registration. Do not silently update another installation.
- User-visible changes: Korean/English README instructions and relevant technical
  documentation. Check the web guide too. Describe tested behavior and unresolved
  limits accurately; update ROADMAP status and put dated results in experiments.
- Packaging changes: manifest completeness, resource references, installation and
  removal from the actual archive. Exclude this development guide, development
  tooling, tests, private configuration, and generated research data. The release
  workflow places the canonical product rules at the archive's root AGENTS.md.
- Version changes: keep pyproject.toml as the version source, refresh uv.lock when
  needed, and require the release tag to match before publishing.

## Validation

Run the focused tests for the changed behavior first. Before a release, run:

```sh
bash scripts/reproduce-validation.sh full
.venv/bin/python -B scripts/check_release_version.py
.venv/bin/python -B scripts/check_guides.py
```

The full test command skips opt-in platform/permission integrations. Report skips
and any checks that could not run; a passing unit suite does not prove actual
Codex sandbox behavior. Use disposable fixtures for any authorized integration
check. Review the final diff and release contents before committing or publishing;
state what changed, what was verified, and whether a release was actually posted.
