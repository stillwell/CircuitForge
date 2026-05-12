"""Property panel — right-hand sidebar showing the selected component's fields."""

from ._qt import QtCore, QtWidgets


class PropertyPanel(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout(self)
        self._fields = {}
        self.title = QtWidgets.QLabel("(no selection)")
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addRow(self.title)
        self._layout = layout
        self.component = None

    def show_component(self, component):
        for f in self._fields.values():
            f.deleteLater()
        self._fields.clear()
        self.component = component
        if component is None:
            self.title.setText("(no selection)")
            return
        self.title.setText(f"{component.ref} — {type(component).__name__}")

        def add(label, value, key):
            edit = QtWidgets.QLineEdit(str(value))
            self._fields[key] = edit
            self._layout.addRow(label, edit)
            edit.editingFinished.connect(lambda k=key, e=edit: self._on_edit(k, e.text()))

        add("Reference", component.ref, "ref")
        add("Value", component.value, "value")
        add("Footprint", component.footprint or "", "footprint")
        add("Rotation", component.rotation, "rotation")
        for pin in component.pins:
            add(f"Pin {pin.name}", pin.net or "", f"pin:{pin.name}")

    def _on_edit(self, key, text):
        c = self.component
        if c is None:
            return
        if key == "ref":
            c.ref = text
        elif key == "value":
            from circuitforge.core.units import parse_value
            try:
                c.value = parse_value(text)
            except ValueError:
                c.value = text
        elif key == "footprint":
            c.footprint = text or None
        elif key == "rotation":
            try:
                c.rotation = int(float(text))
            except ValueError:
                pass
        elif key.startswith("pin:"):
            pin_name = key[len("pin:"):]
            try:
                c.connect(pin_name, text or None)
            except KeyError:
                pass
