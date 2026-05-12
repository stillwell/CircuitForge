"""Qt binding shim — tries PyQt5 first, then PySide6.

Provides a unified `Qt` namespace so the rest of the GUI code doesn't care
which binding is installed.
"""

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    BINDING = "PyQt5"
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        BINDING = "PySide6"
    except ImportError as e:
        raise ImportError(
            "CircuitForge GUI needs PyQt5 or PySide6; install with "
            "`pip install PyQt5` or `pip install PySide6`"
        ) from e
