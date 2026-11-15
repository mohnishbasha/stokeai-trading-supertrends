# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Version and commit.

The image sets SUPERTRENDS_VERSION and SUPERTRENDS_COMMIT from build args. Outside the image
the version comes from the installed package metadata (derived from the root VERSION file) and
the commit from the source checkout, or "unknown" when there is none.
"""

import os
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

_SOURCE_DIR = Path(__file__).resolve().parent
_GIT_TIMEOUT_SECONDS = 2.0

LICENSE_NOTICE = "Copyright Serverless Ventures LLC. Noncommercial use only."
DEFAULT_SOURCE_URL = "https://github.com/mohnishbasha/stokeai-trading-supertrends"


def get_version() -> str:
    """Return the semantic version, without a "v" prefix."""
    env = os.environ.get("SUPERTRENDS_VERSION", "").strip()
    if env:
        return env
    try:
        return package_version("supertrends")
    except PackageNotFoundError:
        return "0.0.0"


def get_commit() -> str:
    """Return the short commit hash, or "unknown"."""
    env = os.environ.get("SUPERTRENDS_COMMIT", "").strip()
    if env:
        return env
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        out = subprocess.run(  # noqa: S603 (fixed argv, no user input)
            [git, "rev-parse", "--short", "HEAD"],
            cwd=_SOURCE_DIR,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def source_url() -> str:
    """Return the license and source link shown next to the notice."""
    return os.environ.get("SUPERTRENDS_SOURCE_URL", "").strip() or DEFAULT_SOURCE_URL
