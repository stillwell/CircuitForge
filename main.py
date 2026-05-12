#!/usr/bin/env python3
"""CircuitForge launcher.

If run without arguments, launches the GUI. Otherwise dispatches to the CLI.
"""

import sys


def _has_qt():
    try:
        import PyQt5  # noqa: F401
        return True
    except ImportError:
        try:
            import PySide6  # noqa: F401
            return True
        except ImportError:
            return False


if __name__ == "__main__":
    if len(sys.argv) == 1:
        if _has_qt():
            from circuitforge.app import run
            sys.exit(run())
        print("PyQt5/PySide6 not installed — falling back to CLI help.")
        from circuitforge.cli import main
        sys.exit(main(["--help"]))
    else:
        from circuitforge.cli import main
        sys.exit(main(sys.argv[1:]))
