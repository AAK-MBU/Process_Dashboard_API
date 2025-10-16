"""
Update version script.

This script updates the version number across all project files.
Version is managed in pyproject.toml as single source of truth.
"""

import re
import subprocess
import sys
from pathlib import Path


def update_version(new_version: str) -> None:
    """
    Update version in all project files.

    Args:
        new_version: New version string (e.g., "1.0.1", "2.0.0")
    """
    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print(f"Invalid version format: {new_version}")
        print("Expected format: X.Y.Z (e.g., 1.0.0)")
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    files_updated = []

    # 1. Update pyproject.toml
    pyproject_path = project_root / "pyproject.toml"
    update_toml_version(pyproject_path, new_version)
    files_updated.append("pyproject.toml")

    # 2. Update .env.example
    env_example = project_root / ".env.example"
    if env_example.exists():
        update_env_version(env_example, new_version)
        files_updated.append(".env.example")

    # 3. Update Dockerfile
    dockerfile = project_root / "Dockerfile"
    if dockerfile.exists():
        update_dockerfile_version(dockerfile, new_version)
        files_updated.append("Dockerfile")

    # Print summary
    print(f"\nVersion updated to {new_version}\n")
    print("Updated files:")
    for file in files_updated:
        print(f"  ✓ {file}")

    # Run uv lock to update the lock file
    print("\nUpdating uv.lock...")
    try:
        result = subprocess.run(
            ["uv", "lock"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        print("  ✓ uv.lock updated successfully")
        if result.stdout:
            print(f"\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to update uv.lock: {e}")
        print(f"    Error output: {e.stderr}")
        print("\nPlease run 'uv lock' manually")
    except FileNotFoundError:
        print("  ✗ 'uv' command not found")
        print("\nPlease run 'uv lock' manually")

    print("\nNote: Check and update .env manually if needed")
    print("Current .env has version that may differ from code")


def update_toml_version(file_path: Path, new_version: str) -> None:
    """Update version in pyproject.toml."""
    content = file_path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE,
    )
    file_path.write_text(updated, encoding="utf-8")


def update_env_version(file_path: Path, new_version: str) -> None:
    """Update version in .env files."""
    content = file_path.read_text(encoding="utf-8")
    updated = re.sub(r'APP_VERSION="[^"]+"', f'APP_VERSION="{new_version}"', content)
    file_path.write_text(updated, encoding="utf-8")


def update_dockerfile_version(file_path: Path, new_version: str) -> None:
    """Update version in Dockerfile."""
    content = file_path.read_text(encoding="utf-8")
    updated = re.sub(r'version="[^"]+"', f'version="{new_version}"', content)
    file_path.write_text(updated, encoding="utf-8")


def get_current_version() -> str:
    """Get current version from pyproject.toml."""
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"

    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)

    if match:
        return match.group(1)
    return "unknown"


def bump_version(current: str, bump_type: str) -> str:
    """
    Bump version number.

    Args:
        current: Current version string (e.g., "1.0.0")
        bump_type: Type of bump: major, minor, or patch

    Returns:
        New version string
    """
    parts = current.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


if __name__ == "__main__":
    current = get_current_version()
    print(f"Current version: {current}\n")

    if len(sys.argv) < 2:
        print("Usage: python update_version.py <new_version|bump_type>")
        print("\nExamples:")
        print("  python scripts/update_version.py 1.0.1")
        print("  python scripts/update_version.py patch   # 1.0.0 -> 1.0.1")
        print("  python scripts/update_version.py minor   # 1.0.1 -> 1.1.0")
        print("  python scripts/update_version.py major   # 1.1.0 -> 2.0.0")
        sys.exit(1)

    arg = sys.argv[1]

    if arg in ("major", "minor", "patch"):
        next_version = bump_version(current, arg)
        print(f"Bumping {arg} version: {current} -> {next_version}\n")
    else:
        next_version = arg

    update_version(next_version)
