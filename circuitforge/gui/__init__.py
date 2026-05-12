"""Qt GUI for CircuitForge — optional, requires PyQt5 or PySide6."""

try:
    from .main_window import MainWindow
    from .component_panel import ComponentPanel
    from .property_panel import PropertyPanel
    from .scope import Scope
    HAS_GUI = True
except ImportError:
    HAS_GUI = False
    MainWindow = ComponentPanel = PropertyPanel = Scope = None

__all__ = ["MainWindow", "ComponentPanel", "PropertyPanel", "Scope", "HAS_GUI"]
