from __future__ import annotations

from importlib.metadata import version

PACKAGE_NAME = "amane"


def get_version() -> str:
    """已安装包的版本 (``pyproject.toml`` → dist-info). 未安装则 ``PackageNotFoundError``."""
    return version(PACKAGE_NAME)
