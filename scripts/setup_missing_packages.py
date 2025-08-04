#!/usr/bin/env python3
"""
Script to create placeholder packages for missing optional dependencies.
This is primarily used in CI environments where optional private packages
may not be available.
"""

from pathlib import Path


def create_placeholder_miranda_admin_ops():
    """Create a minimal placeholder miranda_admin_ops package."""
    package_dir = Path("packages/miranda_admin_ops")
    pyproject_file = package_dir / "pyproject.toml"

    if pyproject_file.exists():
        print("✓ miranda_admin_ops already exists")
        return

    print("Creating placeholder miranda_admin_ops package...")

    # Create package directory
    package_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal pyproject.toml
    pyproject_content = """[project]
name = "miranda_admin_ops"
version = "0.0.1"
description = "Placeholder package for miranda_admin_ops"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["miranda_admin_ops"]
"""

    with open(package_dir / "pyproject.toml", "w") as f:
        f.write(pyproject_content)

    # Create minimal __init__.py
    init_content = '''"""
Placeholder miranda_admin_ops package.
This is a minimal stub package created when the real miranda_admin_ops
package is not available (e.g., in CI environments without access to private repos).
"""
'''

    with open(package_dir / "__init__.py", "w") as f:
        f.write(init_content)

    print("✓ Created placeholder miranda_admin_ops package")


def main():
    """Main entry point."""
    print("Setting up missing packages...")
    create_placeholder_miranda_admin_ops()
    print("✓ Setup complete")


if __name__ == "__main__":
    main()
