# Research Agent development

This is the development checkout. Product operation rules live in
[resources/AGENTS.runtime.md](resources/AGENTS.runtime.md); read them before
changing behavior or operating the library. The personal skill and registered
agents load that canonical product file, not this development guide. Runtime
restrictions on generated library data do not prohibit authorized source-code,
test, or documentation changes in this checkout.

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
  documentation. Describe tested behavior and unresolved limits accurately.
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
```

The full test command skips opt-in platform/permission integrations. Report skips
and any checks that could not run; a passing unit suite does not prove actual
Codex sandbox behavior. Use disposable fixtures for any authorized integration
check. Review the final diff and release contents before committing or publishing;
state what changed, what was verified, and whether a release was actually posted.
