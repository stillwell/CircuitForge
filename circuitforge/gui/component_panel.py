"""Component palette — left-hand sidebar listing parts in the library."""

from ._qt import QtCore, QtGui, QtWidgets


class ComponentPanel(QtWidgets.QWidget):

    component_selected = QtCore.pyqtSignal(str) if hasattr(QtCore, "pyqtSignal") \
        else QtCore.Signal(str)

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        layout = QtWidgets.QVBoxLayout(self)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search components…")
        layout.addWidget(self.search)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Component", "Description"])
        layout.addWidget(self.tree)
        self.search.textChanged.connect(self._on_search)
        self.tree.itemActivated.connect(self._on_activate)
        self._populate("")

    def _populate(self, query):
        self.tree.clear()
        by_kind = {}
        for e in self.library:
            if query and query.lower() not in e.name.lower() and \
                    query.lower() not in e.description.lower():
                continue
            by_kind.setdefault(e.kind, []).append(e)
        for kind, entries in sorted(by_kind.items()):
            group = QtWidgets.QTreeWidgetItem([kind, ""])
            self.tree.addTopLevelItem(group)
            for e in sorted(entries, key=lambda x: x.name):
                item = QtWidgets.QTreeWidgetItem([e.name, e.description])
                group.addChild(item)
            group.setExpanded(bool(query))
        self.tree.resizeColumnToContents(0)

    def _on_search(self, text):
        self._populate(text)

    def _on_activate(self, item):
        if item.parent() is not None:
            self.component_selected.emit(item.text(0))
