"""CircuitForge main window — combines schematic editor, PCB editor, scope."""

from ._qt import QtCore, QtGui, QtWidgets
from .component_panel import ComponentPanel
from .property_panel import PropertyPanel
from .scope import Scope
from .. import resources, __version__, __copyright__, __author__, __email__, show_w, show_c


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, project=None, library=None):
        super().__init__()
        self.setWindowTitle("CircuitForge")
        self.resize(1280, 800)
        self.project = project
        self.library = library

        icon_path = resources.company_logo()
        if icon_path:
            self.setWindowIcon(QtGui.QIcon(icon_path))

        # central tabbed editor
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)
        self.schematic_view = QtWidgets.QGraphicsView(QtWidgets.QGraphicsScene())
        self.pcb_view = QtWidgets.QGraphicsView(QtWidgets.QGraphicsScene())
        self.scope = Scope()
        self.tabs.addTab(self.schematic_view, "Schematic")
        self.tabs.addTab(self.pcb_view, "PCB")
        self.tabs.addTab(self.scope, "Simulation")

        # docks
        if library is not None:
            self.component_panel = ComponentPanel(library)
            dock = QtWidgets.QDockWidget("Components", self)
            dock.setWidget(self.component_panel)
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        self.property_panel = PropertyPanel()
        dock = QtWidgets.QDockWidget("Properties", self)
        dock.setWidget(self.property_panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

        self._build_menus()
        self.statusBar().showMessage("CircuitForge ready.")

    def _build_menus(self):
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        file_menu.addAction("&New project", self._new_project)
        file_menu.addAction("&Open…", self._open_project)
        file_menu.addAction("&Save", self._save_project)
        file_menu.addSeparator()
        import_menu = file_menu.addMenu("&Import")
        import_menu.addAction("KiCAD schematic (.kicad_sch)", self._import_kicad_sch)
        import_menu.addAction("KiCAD board (.kicad_pcb)", self._import_kicad_pcb)
        import_menu.addAction("Eagle schematic (.sch)", self._import_eagle_sch)
        import_menu.addAction("Eagle board (.brd)", self._import_eagle_brd)
        import_menu.addAction("SPICE netlist (.cir/.sp)", self._import_spice)
        export_menu = file_menu.addMenu("&Export")
        export_menu.addAction("KiCAD schematic", self._export_kicad_sch)
        export_menu.addAction("KiCAD board", self._export_kicad_pcb)
        export_menu.addAction("Gerber set", self._export_gerber)
        export_menu.addAction("Excellon drill", self._export_drill)
        export_menu.addAction("SPICE netlist", self._export_spice)
        export_menu.addAction("BOM (CSV)", self._export_bom)
        export_menu.addAction("SVG", self._export_svg)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction("Undo", lambda: None, "Ctrl+Z")
        edit_menu.addAction("Redo", lambda: None, "Ctrl+Y")

        sim_menu = bar.addMenu("&Simulate")
        sim_menu.addAction("DC Operating Point", self._sim_op)
        sim_menu.addAction("DC Sweep…",        self._sim_dc)
        sim_menu.addAction("AC Analysis…",     self._sim_ac)
        sim_menu.addAction("Transient…",       self._sim_tran)

        pcb_menu = bar.addMenu("&PCB")
        pcb_menu.addAction("Autoroute (Lee)",  self._autoroute)
        pcb_menu.addAction("DRC",              self._drc)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction("About", self._about)

    # --- file ops (stubs) ---
    def _new_project(self):
        from circuitforge.core.project import Project
        self.project = Project()
        self.statusBar().showMessage("New project.")

    def _open_project(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open project", "", "CircuitForge (*.cfproj)")
        if path:
            from circuitforge.core.project import Project
            self.project = Project.load(path)
            self.statusBar().showMessage(f"Opened {path}")

    def _save_project(self):
        if self.project is None:
            self._new_project()
        path = self.project.path
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save project", "", "CircuitForge (*.cfproj)")
            if not path:
                return
        self.project.save(path)
        self.statusBar().showMessage(f"Saved {path}")

    # --- import ---
    def _import_kicad_sch(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import KiCAD schematic", "", "*.kicad_sch")
        if not path: return
        from circuitforge.io import read_kicad_sch
        canvas = read_kicad_sch(path)
        self.statusBar().showMessage(
            f"Imported {len(canvas.placements)} symbols from {path}")

    def _import_kicad_pcb(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import KiCAD board", "", "*.kicad_pcb")
        if not path: return
        from circuitforge.io import read_kicad_pcb
        board = read_kicad_pcb(path)
        self.statusBar().showMessage(f"Imported board: {board.stats()}")

    def _import_eagle_sch(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Eagle schematic", "", "*.sch")
        if not path: return
        from circuitforge.io import read_eagle_sch
        nl = read_eagle_sch(path)
        self.statusBar().showMessage(nl.summary())

    def _import_eagle_brd(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Eagle board", "", "*.brd")
        if not path: return
        from circuitforge.io import read_eagle_brd
        board = read_eagle_brd(path)
        self.statusBar().showMessage(f"Imported board: {board.stats()}")

    def _import_spice(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import SPICE deck", "", "*.cir *.sp *.net")
        if not path: return
        from circuitforge.io import read_spice_deck
        nl, _dirs = read_spice_deck(path)
        self.statusBar().showMessage(nl.summary())

    # --- export ---
    def _export_kicad_sch(self): self._not_implemented("export KiCAD sch")
    def _export_kicad_pcb(self): self._not_implemented("export KiCAD pcb")
    def _export_gerber(self):    self._not_implemented("export Gerber set")
    def _export_drill(self):     self._not_implemented("export drill")
    def _export_spice(self):     self._not_implemented("export SPICE")
    def _export_bom(self):       self._not_implemented("export BOM")
    def _export_svg(self):       self._not_implemented("export SVG")

    # --- simulations ---
    def _sim_op(self):    self._not_implemented("DC operating point")
    def _sim_dc(self):    self._not_implemented("DC sweep")
    def _sim_ac(self):    self._not_implemented("AC analysis")
    def _sim_tran(self):  self._not_implemented("Transient")

    # --- pcb ---
    def _autoroute(self): self._not_implemented("autoroute")
    def _drc(self):       self._not_implemented("DRC")

    def _about(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("About CircuitForge")
        layout = QtWidgets.QVBoxLayout(dlg)

        banner_path = resources.banner()
        if banner_path:
            pix = QtGui.QPixmap(banner_path).scaledToWidth(
                560, QtCore.Qt.SmoothTransformation)
            banner = QtWidgets.QLabel()
            banner.setPixmap(pix)
            banner.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(banner)

        text = QtWidgets.QLabel(
            f"<h2>CircuitForge {__version__}</h2>"
            "<p>Open-source EDA suite — schematic capture, "
            "SPICE-style circuit simulation, and PCB layout.</p>"
            f"<p>{__copyright__} &lt;<a href='https://www.enlightec.com'>"
            "www.enlightec.com</a>&gt;<br>"
            f"Author: <b>{__author__}</b> "
            f"&lt;<a href='mailto:{__email__}'>{__email__}</a>&gt;</p>"
            "<p style='color:#888;font-size:11px'>"
            "This program comes with ABSOLUTELY NO WARRANTY; for details "
            "see <a href='#warranty'>Warranty</a>. This is free software, "
            "and you are welcome to redistribute it under the terms of the "
            "GNU GPL v3 — see <a href='#conditions'>Conditions</a>.</p>")
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        text.setAlignment(QtCore.Qt.AlignCenter)
        def _on_link(href):
            if href == "#warranty":
                QtWidgets.QMessageBox.information(dlg, "Warranty", show_w())
            elif href == "#conditions":
                QtWidgets.QMessageBox.information(dlg, "Conditions", show_c())
        text.linkActivated.connect(_on_link)
        layout.addWidget(text)

        logo_path = resources.company_logo()
        if logo_path:
            pix = QtGui.QPixmap(logo_path).scaledToWidth(
                180, QtCore.Qt.SmoothTransformation)
            logo = QtWidgets.QLabel()
            logo.setPixmap(pix)
            logo.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(logo)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.resize(620, 560)
        dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()

    def _not_implemented(self, what):
        QtWidgets.QMessageBox.information(self, "CircuitForge",
            f"{what} — not yet wired to GUI. "
            "Use the CLI (`python -m circuitforge.cli`) or the API.")
