from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def choose_file(prompt: str) -> Path | None:
    """Open the native macOS file chooser and return the selected file."""
    if platform.system() != "Darwin":
        raise RuntimeError("Choose is available only on macOS.")

    escaped_prompt = prompt.replace('"', '\\"')
    script = f'POSIX path of (choose file with prompt "{escaped_prompt}")'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # AppleScript returns a non-zero status when the chooser is cancelled.
        if "User canceled" in result.stderr or "(-128)" in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip() or "Unable to open file chooser.")
    selected = result.stdout.strip()
    return Path(selected) if selected else None


def reveal_file(path: Path) -> None:
    """Reveal the managed document in Finder without opening or editing it."""
    if not path.is_file():
        raise ValueError("No managed file exists.")
    if platform.system() != "Darwin":
        raise RuntimeError("View is available only on macOS.")
    subprocess.run(["open", "-R", str(path.resolve())], check=True,
                   capture_output=True, text=True)
