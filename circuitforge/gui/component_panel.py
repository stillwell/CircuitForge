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
        self.db_query.setPlaceholderText(
            "Search MPN / manufacturer / description… (lazy — nothing runs until you type or click Browse)")
        controls.addWidget(self.db_query, 1)
        self.db_source = QtWidgets.QComboBox()
        self.db_source.addItem("(all sources)", "")
        controls.addWidget(self.db_source)
        self.db_page_size = QtWidgets.QComboBox()
        for n in (10, 25, 50, 100, 200):
            self.db_page_size.addItem(f"{n}/page", n)
        self.db_page_size.setCurrentIndex(1)   # 25/page default
        controls.addWidget(self.db_page_size)
        self.db_btn = QtWidgets.QPushButton("Search")
        controls.addWidget(self.db_btn)
        self.db_browse_btn = QtWidgets.QPushButton("Browse")
        self.db_browse_btn.setToolTip("List top-stocked parts (no search query)")
        controls.addWidget(self.db_browse_btn)
        v.addLayout(controls)

        self.db_status = QtWidgets.QLabel("(DB tab idle — search above or hit Browse.)")
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

        # Paginator
        pager = QtWidgets.QHBoxLayout()
        self.db_first_btn = QtWidgets.QPushButton("⏮ First")
        self.db_prev_btn  = QtWidgets.QPushButton("‹ Prev")
        self.db_page_lbl  = QtWidgets.QLabel("Page —")
        self.db_page_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.db_next_btn  = QtWidgets.QPushButton("Next ›")
        pager.addWidget(self.db_first_btn)
        pager.addWidget(self.db_prev_btn)
        pager.addWidget(self.db_page_lbl, 1)
        pager.addWidget(self.db_next_btn)
        for b in (self.db_first_btn, self.db_prev_btn, self.db_next_btn):
            b.setEnabled(False)
        v.addLayout(pager)

        # Pagination state
        self._db_page = 1
        self._db_initialised = False

        # Wire up
        self.db_btn.clicked.connect(self._on_db_search)
        self.db_browse_btn.clicked.connect(self._on_db_browse)
        self.db_query.returnPressed.connect(self._on_db_search)
        self.db_source.currentIndexChanged.connect(self._on_db_filter_changed)
        self.db_page_size.currentIndexChanged.connect(self._on_db_filter_changed)
        self.db_first_btn.clicked.connect(lambda: self._go_page(1))
        self.db_prev_btn.clicked.connect(lambda: self._go_page(self._db_page - 1))
        self.db_next_btn.clicked.connect(lambda: self._go_page(self._db_page + 1))

        self.tabs.addTab(tab, "Database")
        QtCore.QTimer.singleShot(0, self._init_db_lazy)

    def _init_db_lazy(self):
        """Cheap probe — uses O(1) fast_count_estimate; runs no expensive
        query. Populates the sources dropdown and the status line only."""
        try:
            from circuitforge.database import ComponentDB
            with ComponentDB() as db:
                est = db.fast_count_estimate()
                if est == 0:
                    self.db_status.setText(
                        "Database is empty. Run "
                        "<code>circuitforge library sync --source local</code> "
                        "(or any other loader) to populate it.")
                    return
                for s in db.sources():
                    self.db_source.addItem(s, s)
                self.db_status.setText(
                    f"~{est:,} components available. Type to search or "
                    f"hit <b>Browse</b> to list the first page.")
                self._db_initialised = True
        except Exception as e:
            self.db_status.setText(f"DB unavailable: {e}")

    def _on_db_search(self, *_):
        self._db_page = 1
        self._do_search()

    def _on_db_browse(self):
        self.db_query.clear()
        self._db_page = 1
        self._do_search()

    def _on_db_filter_changed(self, *_):
        if self._db_initialised:
            self._db_page = 1
            self._do_search()

    def _go_page(self, page):
        self._db_page = max(1, page)
        self._do_search()

    def _do_search(self):
        if not self._db_initialised:
            return
        query = self.db_query.text()
        source = self.db_source.currentData() or None
        page_size = self.db_page_size.currentData() or 25
        page = self._db_page
        try:
            from circuitforge.database import ComponentDB
            db = ComponentDB()
            rows = db.search(query, source=source,
                             limit=page_size + 1,
                             offset=(page - 1) * page_size)
            has_next = len(rows) > page_size
            rows = rows[:page_size]
            db.close()
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

        start = (page - 1) * page_size + 1
        end = start + len(rows) - 1 if rows else start - 1
        self.db_page_lbl.setText(f"Page {page} — rows {start:,}–{end:,}")
        self.db_first_btn.setEnabled(page > 1)
        self.db_prev_btn.setEnabled(page > 1)
        self.db_next_btn.setEnabled(has_next)
        self.db_status.setText(
            f"{len(rows)} rows returned "
            f"(query={query!r}, source={source or 'any'}, {page_size}/page)")
        self.db_table.resizeColumnsToContents()

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
