import contextlib
import os
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
