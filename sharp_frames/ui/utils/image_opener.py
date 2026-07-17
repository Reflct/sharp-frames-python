"""Open analyzed frame images with the platform's default viewer."""

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional


def open_image_file(path: str, system_name: Optional[str] = None) -> None:
    """Open an existing image without blocking the Textual application."""
    image_path = Path(path).expanduser()
    if not image_path.is_file():
        raise FileNotFoundError(f"Frame image is no longer available: {image_path}")

    current_system = system_name or platform.system()
    if current_system == "Windows":
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise OSError("Windows image opener is unavailable")
        startfile(str(image_path))
        return

    command = ["open", str(image_path)] if current_system == "Darwin" else [
        "xdg-open",
        str(image_path),
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            start_new_session=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError(f"Unable to launch the default image viewer: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise OSError(f"Unable to launch the default image viewer: {detail}")
