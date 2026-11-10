"""Cross-terminal clipboard support for the custom inline editor.

macOS Terminal does not implement Textual's OSC-52 copy protocol. For local
macOS sessions use pbcopy (the OS clipboard), without shell interpolation.
Other terminals can use Textual's clipboard method as a fallback.
"""
from __future__ import annotations

import platform
import subprocess


def copy_native_clipboard(text: str) -> bool:
    """Copy on macOS; return False when the caller should use OSC-52 instead.

    Raises OSError or CalledProcessError if pbcopy fails, so callers can
    display an error instead of claiming the text was copied.
    """
    if platform.system() != "Darwin":
        return False
    subprocess.run(
        ["pbcopy"], input=text, text=True, check=True, capture_output=True,
    )
    return True
