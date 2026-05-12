"""Component palette — left-hand sidebar.

Two tabs:
  Library  — bundled JSON catalogue (the ~108 entries in libs/components.json)
  Database — DB-backed catalogue once any loader has run (millions of parts).
             Each row carries vendor-link icon buttons that open the
             vendor's product page in the system browser.
"""

import os

from ._qt import QtCore, QtGui, QtWidgets

try:
    _SIGNAL = QtCore.pyqtSignal
except AttributeError:
    _SIGNAL = QtCore.Signal


VENDOR_ICONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "web", "static", "vendor-icons")


def _vendor_icon(name):
    path = os.path.abspath(os.path.join(VENDOR_ICONS_DIR, f"{name}.svg"))
    return QtGui.QIcon(path) if os.path.exists(path) else QtGui.QIcon()


class ComponentPanel(QtWidgets.QWidget):

    component_selected = _SIGNAL(str)

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library

        layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self._build_library_tab()
        self._build_database_tab()

    # ---------- JSON-bundle tab ----------
    def _build_library_tab(self):
        tab = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(tab)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search components…")
        v.addWidget(self.search)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Component", "Description"])
        v.addWidget(self.tree)
        self.search.textChanged.connect(self._on_search)
        self.tree.itemActivated.connect(self._on_activate)
        self._populate("")
        self.tabs.addTab(tab, "Library")

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

    # ---------- DB-backed tab ----------
    def _build_database_tab(self):
        tab = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(tab)

        controls = QtWidgets.QHBoxLayout()
        self.db_query = QtWidgets.QLineEdit()
        self.db_query.setPlaceholderText("Search MPN / manufacturer / description…")
        controls.addWidget(self.db_query, 1)
        self.db_source = QtWidgets.QComboBox()
        self.db_source.addItem("(all sources)", "")
        controls.addWidget(self.db_source)
        self.db_btn = QtWidgets.QPushButton("Search")
        controls.addWidget(self.db_btn)
        v.addLayout(controls)

        self.db_status = QtWidgets.QLabel("(DB not yet populated)")
        self.db_status.setStyleSheet("color: #888; padding: 4px;")
        v.addWidget(self.db_status)

        self.db_table = QtWidgets.QTableWidget(0, 6)
        self.db_table.setHorizontalHeaderLabels(
            ["Src", "MPN / Name", "Manufacturer", "Package", "Stock",
             "Vendor links"])
        self.db_table.horizontalHeader().setStretchLastSection(True)
        self.db_table.verticalHeader().setVisible(False)
        self.db_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        v.addWidget(self.db_table, 1)

        self.db_btn.clicked.connect(self._on_db_search)
        self.db_query.returnPressed.connect(self._on_db_search)
        self.db_source.currentIndexChanged.connect(self._on_db_search)
        self.tabs.addTab(tab, "Database")

        # Populate source dropdown + initial search
        QtCore.QTimer.singleShot(0, self._init_db)

    def _init_db(self):
        try:
            from circuitforge.database import ComponentDB
            with ComponentDB() as db:
                total = db.count()
                if total == 0:
                    self.db_status.setText(
                        "Database is empty. Run "
                        "<code>circuitforge library sync --source local</code> "
                        "or another loader to populate it.")
                    return
                for s in db.sources():
                    self.db_source.addItem(s, s)
                self.db_status.setText(
                    f"{total:,} components across {len(db.sources())} source(s).")
                self._do_search("", "", limit=50)
        except Exception as e:
            self.db_status.setText(f"DB unavailable: {e}")

    def _on_db_search(self, *_):
        q = self.db_query.text()
        src = self.db_source.currentData() or None
        self._do_search(q, src, limit=100)

    def _do_search(self, query, source, limit):
        try:
            from circuitforge.database import ComponentDB, vendor_links
            with ComponentDB() as db:
                rows = db.search(query, source=source, limit=limit)
        except Exception as e:
            self.db_status.setText(f"DB error: {e}")
            return

        self.db_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.db_table.setItem(i, 0, QtWidgets.QTableWidgetItem(r.source))
            self.db_table.setItem(i, 1, QtWidgets.QTableWidgetItem(r.mpn or r.name))
            self.db_table.setItem(i, 2, QtWidgets.QTableWidgetItem(r.manufacturer))
            self.db_table.setItem(i, 3, QtWidgets.QTableWidgetItem(r.package))
            stock_item = QtWidgets.QTableWidgetItem(f"{r.stock:,}" if r.stock else "")
            stock_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.db_table.setItem(i, 4, stock_item)

            self.db_table.setCellWidget(i, 5, self._build_link_row(r))

        self.db_table.resizeColumnsToContents()
        self.db_status.setText(f"{len(rows)} results "
                               f"(query={query!r}, source={source or 'any'})")

    def _build_link_row(self, record):
        from circuitforge.database import vendor_links
        wrap = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(wrap)
        h.setContentsMargins(2, 0, 2, 0); h.setSpacing(2)
        for lk in vendor_links(record):
            btn = QtWidgets.QToolButton()
            btn.setIcon(_vendor_icon(lk["icon"]))
            btn.setIconSize(QtCore.QSize(20, 20))
            btn.setToolTip(f"{lk['label']} — {lk['url']}")
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QToolButton {{
                    background: {lk['color']};
                    border: none; border-radius: 4px;
                    padding: 2px;
                }}
                QToolButton:hover {{
                    border: 1px solid #fff8;
                }}
            """)
            url = lk["url"]
            btn.clicked.connect(lambda _, u=url: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(u)))
            h.addWidget(btn)
        h.addStretch(1)
        return wrap
