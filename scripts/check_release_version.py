#!/usr/bin/env python3
"""Read-only preflight for version metadata; does not build or publish a release."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib


RELEASE_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


class ReleaseVersionError(ValueError):
    """Release metadata is missing, ambiguous, or inconsistent."""


def read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, ValueError) as exc:
        raise ReleaseVersionError(f"Cannot read {path.name}: {exc}") from exc


def check_release_version(root: Path, tag: str | None = None) -> str:
    project = read_toml(root / "pyproject.toml").get("project")
    if not isinstance(project, dict) or project.get("name") != "research-store":
        raise ReleaseVersionError("pyproject.toml must define [project].name = 'research-store'.")
    version = project.get("version")
    if not isinstance(version, str) or not RELEASE_VERSION.fullmatch(version):
        raise ReleaseVersionError("pyproject.toml [project].version must use X.Y.Z, for example 0.3.0.")
    dynamic = project.get("dynamic", [])
    if not isinstance(dynamic, list) or any(not isinstance(item, str) for item in dynamic):
        raise ReleaseVersionError("pyproject.toml [project].dynamic must be a list of field names.")
    if "version" in dynamic:
        raise ReleaseVersionError("[project].version must be static, not listed in dynamic.")

    lock = read_toml(root / "uv.lock")
    if type(lock.get("version")) is not int or lock["version"] != 1:
        raise ReleaseVersionError("uv.lock must use the supported lock format version 1.")
    packages = lock.get("package")
    if not isinstance(packages, list) or any(not isinstance(item, dict) for item in packages):
        raise ReleaseVersionError("uv.lock must contain [[package]] records.")
    roots = [
        item
        for item in packages
        if item.get("name") == "research-store"
        and isinstance(item.get("source"), dict)
        and item["source"].get("editable") == "."
    ]
    if len(roots) != 1:
        raise ReleaseVersionError(
            "uv.lock must contain exactly one research-store package with source = { editable = '.' }."
        )
    lock_version = roots[0].get("version")
    if not isinstance(lock_version, str) or not RELEASE_VERSION.fullmatch(lock_version):
        raise ReleaseVersionError("The editable research-store version in uv.lock must use X.Y.Z.")
    if lock_version != version:
        raise ReleaseVersionError(
            f"Version mismatch: pyproject.toml is {version}, but editable research-store in uv.lock is {lock_version}."
        )
    if tag is not None and tag != f"v{version}":
        raise ReleaseVersionError(f"Tag mismatch: expected 'v{version}', got {tag!r}.")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="Repository containing pyproject.toml and uv.lock (defaults to this script's repository).",
    )
    parser.add_argument("--tag", help="Optional release tag; must equal v followed by [project].version.")
    args = parser.parse_args(argv)
    try:
        version = check_release_version(args.root, args.tag)
    except ReleaseVersionError as exc:
        print(f"Release version check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Version: {version}")
    print(f"Expected tag: v{version}")
    print(f"Runtime archive name (not created): research-agent-{version}.tar.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
