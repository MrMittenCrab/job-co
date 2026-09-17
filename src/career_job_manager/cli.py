from __future__ import annotations

import platform
import sys

from .ui import CareerApp


def main() -> None:
    if platform.system() != "Darwin":
        print("Career Job Manager Version 1 is designed for macOS.", file=sys.stderr)
        raise SystemExit(2)
    CareerApp().run()


if __name__ == "__main__":
    main()
