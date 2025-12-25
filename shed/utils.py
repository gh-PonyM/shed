import contextlib
import os
import shutil
import subprocess
from pathlib import Path


@contextlib.contextmanager
def cd_to_directory(path: Path, env: dict | None = None):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def is_ruff_available() -> bool:
    """Check if ruff is available in the current environment."""
    return shutil.which("ruff") is not None


def format_with_ruff(file_path: Path) -> bool:
    """
    Format a file with ruff.

    Returns True if formatting was successful, False otherwise.
    """
    if not is_ruff_available():
        return False

    try:
        result = subprocess.run(
            ["ruff", "format", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
