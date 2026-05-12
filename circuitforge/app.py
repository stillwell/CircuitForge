"""GUI application entry point."""

import sys


def run(argv=None):
    """Launch the Qt GUI. Returns the Qt event-loop exit code."""
    from .gui._qt import QtWidgets
    from .gui.main_window import MainWindow
    from .components.library import ComponentLibrary

    argv = argv or sys.argv
    app = QtWidgets.QApplication(argv)
    library = ComponentLibrary().load_default()
    window = MainWindow(library=library)
    window.show()
    return app.exec_() if hasattr(app, "exec_") else app.exec()


if __name__ == "__main__":
    sys.exit(run())
