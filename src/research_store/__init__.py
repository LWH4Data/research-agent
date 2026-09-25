"""Local read-only PDF research store."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def _resolve_version() -> str:
    # A checkout (including an editable install) uses its own pyproject so a
    # version edit cannot be hidden by stale installed distribution metadata.
    package = Path(__file__).resolve().parent
    if package.name == "research_store" and package.parent.name == "src":
        project_file = package.parent.parent / "pyproject.toml"
        if project_file.is_file():
            with project_file.open("rb") as stream:
                project = tomllib.load(stream).get("project", {})
            if project.get("name") == "research-store":
                project_version = project.get("version")
                if not isinstance(project_version, str) or not project_version.strip():
                    raise ValueError("research-store project.version must be a non-empty string")
                return project_version

    # Wheels do not contain the source pyproject. Their installed metadata is
    # generated from the same authoritative project.version at build time.
    try:
        return version("research-store")
    except PackageNotFoundError:
        # Some isolated fixtures copy only src, with no distribution metadata.
        return "0+unknown"


__version__ = _resolve_version()
