"""Oude Mechanismen procedural engine core package.

This package provides foundational components for the oude-mechanismen
procedural execution engine, including CLI utilities and asset resolution
for both editable and installed wheel distributions.
"""

from pathlib import Path

__all__ = ["PACKAGE_DIR", "ENGINE_ROOT", "resolve_asset_dir", "__version__"]

PACKAGE_DIR: Path = Path(__file__).resolve().parent
ENGINE_ROOT: Path = PACKAGE_DIR.parent.parent


def _get_version() -> str:
    """Resolve package version from VERSION file or installed metadata."""
    for candidate in [PACKAGE_DIR / "VERSION", ENGINE_ROOT / "VERSION"]:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    try:
        from importlib.metadata import version
        return version("oude-mechanismen")
    except Exception:
        return "0.5.0"


__version__: str = _get_version()


def resolve_asset_dir(name: str) -> Path:
    """Resolve an asset directory path.

    Checks the package directory first (when installed as a wheel with
    force-include), then falls back to the engine root directory (when
    running in an editable checkout).

    Args:
        name: The name of the asset directory or file to resolve.

    Returns:
        The resolved absolute path to the asset directory.
    """
    candidate = PACKAGE_DIR / name
    if candidate.exists():
        return candidate
    return ENGINE_ROOT / name
