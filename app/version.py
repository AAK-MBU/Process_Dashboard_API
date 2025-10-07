"""Version management - single source of truth."""

import tomllib
from pathlib import Path

# Root directory of the project
PROJECT_ROOT = Path(__file__).parent.parent


def get_version() -> str:
    """
    Get version from pyproject.toml - single source of truth.

    Returns:
        Version string (e.g., "1.0.0")
    """
    pyproject_path = PROJECT_ROOT / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)

    return pyproject_data["project"]["version"]


# Export version as module-level constant
__version__ = get_version()
