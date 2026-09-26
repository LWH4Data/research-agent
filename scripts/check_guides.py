#!/usr/bin/env python3
"""Check installation instructions without running or downloading anything."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tomllib


class GuideError(ValueError):
    """User-facing installation guides disagree or have incomplete metadata."""


def normalize(command: str) -> str:
    return "\n".join(line.rstrip() for line in command.strip().splitlines())


def installation_block(path: Path) -> str:
    blocks = re.findall(r"^```(?:sh|bash)\s*\n(.*?)^```\s*$", path.read_text(), re.M | re.S)
    candidates = [block for block in blocks if "install-release.sh" in block]
    if len(candidates) != 1:
        raise GuideError(f"{path}: expected exactly one release installation shell block")
    return normalize(candidates[0])


def check_guides(root: Path) -> str:
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise GuideError("pyproject.toml: expected a static X.Y.Z version")
    config_path = root / "docs/site/config.js"
    assignment = re.fullmatch(
        r"\s*window\.RESEARCH_GUIDE_RELEASE\s*=\s*(\{.*\})\s*;\s*",
        config_path.read_text(), re.S,
    )
    if not assignment:
        raise GuideError(f"{config_path}: expected a JSON release configuration assignment")
    config = json.loads(assignment[1])
    if config.get("version") != version:
        raise GuideError(f"{config_path}: version must match pyproject.toml ({version})")
    if not isinstance(config.get("installCommand"), str) or not config["installCommand"].strip():
        raise GuideError(f"{config_path}: installCommand must be a nonempty string")
    command = normalize(config["installCommand"])
    for relative in ("README.md", "docs/en/user-guide.md"):
        if installation_block(root / relative) != command:
            raise GuideError(f"{relative}: installation command differs from docs/site/config.js")

    # Agreement alone is insufficient: all copies could name an old release or
    # a wrong download host. Check the executable command's two version inputs.
    expected_url = f"https://github.com/LWH4Data/research-agent/releases/download/v{version}/install-release.sh"
    urls = re.findall(r"https?://[^\s\"'<>]+", command)
    if urls != [expected_url]:
        raise GuideError(f"Installation download must be exactly {expected_url}")
    invocations = re.findall(r'^\s*bash\s+"\$installer"\s+--version\s+([^\s]+)\s*$', command, re.M)
    if invocations != [version]:
        raise GuideError(f'Installation must invoke bash "$installer" --version {version}')

    for relative in ("docs/site/app.js", "docs/site/content-en.js"):
        labels = re.findall(r"\bv(\d+\.\d+\.\d+)\b", (root / relative).read_text())
        if any(label != version for label in labels):
            raise GuideError(f"{relative}: a visible release label differs from v{version}")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        version = check_guides(args.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Guide check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Guides agree: v{version}; Korean/English/web installation commands match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
