"""CircuitForge main window — combines schematic editor, PCB editor, scope."""

from ._qt import QtCore, QtGui, QtWidgets
from .component_panel import ComponentPanel
from .property_panel import PropertyPanel
from .scope import Scope
from .dialogs import (SimulationDialog, OpPointDialog, ViolationsDialog,
                      AutorouteDialog)
from .. import resources, __version__, __copyright__, __author__, __email__, show_w, show_c


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, project=None, library=None):
        super().__init__()
        self.setWindowTitle("CircuitForge")
        self.resize(1280, 800)
        self.project = project
        self.library = library
        # Loaded artefacts the simulator/export menus operate on:
        self.current_netlist = None     # circuitforge.core.netlist.Netlist
        self.current_board = None       # circuitforge.pcb.editor.Board
        self.current_canvas = None      # SchematicCanvas
        self.current_result = None      # SimulationResult

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
        self.current_canvas = read_kicad_sch(path)
        self.statusBar().showMessage(
            f"Loaded {len(self.current_canvas.placements)} symbols from {path}")

    def _import_kicad_pcb(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import KiCAD board", "", "*.kicad_pcb")
        if not path: return
        from circuitforge.io import read_kicad_pcb
        self.current_board = read_kicad_pcb(path)
        self.statusBar().showMessage(f"Loaded board: {self.current_board.stats()}")

    def _import_eagle_sch(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Eagle schematic", "", "*.sch")
        if not path: return
        from circuitforge.io import read_eagle_sch
        self.current_netlist = read_eagle_sch(path)
        self.statusBar().showMessage(self.current_netlist.summary())

    def _import_eagle_brd(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Eagle board", "", "*.brd")
        if not path: return
        from circuitforge.io import read_eagle_brd
        self.current_board = read_eagle_brd(path)
        self.statusBar().showMessage(f"Loaded board: {self.current_board.stats()}")

    def _import_spice(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import SPICE deck", "", "SPICE (*.cir *.sp *.net);;All (*)")
        if not path: return
        from circuitforge.io import read_spice_deck
        nl, _dirs = read_spice_deck(path)
        self.current_netlist = nl
        self.statusBar().showMessage(f"Loaded: {nl.summary()}")

    # ---------- guard helpers ----------
    def _require_netlist(self, action):
        if self.current_netlist is None:
            # Offer to open a SPICE deck inline so the user can keep moving.
            r = QtWidgets.QMessageBox.question(
                self, "No netlist loaded",
                f"{action} needs a netlist. Open a SPICE deck now?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if r == QtWidgets.QMessageBox.Yes:
                self._import_spice()
            return self.current_netlist is not None
        return True

    def _require_board(self, action):
        if self.current_board is None:
            r = QtWidgets.QMessageBox.question(
                self, "No board loaded",
                f"{action} needs a PCB. Open a KiCAD board now?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if r == QtWidgets.QMessageBox.Yes:
                self._import_kicad_pcb()
            return self.current_board is not None
        return True

    def _require_canvas(self, action):
        if self.current_canvas is None:
            QtWidgets.QMessageBox.information(
                self, "No schematic loaded",
                f"{action} needs a schematic. Open a KiCAD schematic first.")
            return False
        return True

    def _save_as(self, title, filter_):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, title, "", filter_)
        return path or None

    def _wrap(self, work, success_msg):
        """Run a callable, surface exceptions, update the status bar."""
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            result = work()
        except Exception as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.critical(self, "CircuitForge", f"{type(e).__name__}: {e}")
            return None
        QtWidgets.QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(success_msg)
        return result

    # ---------------- exports ----------------
    def _export_kicad_sch(self):
        if not self._require_canvas("Export KiCAD schematic"): return
        path = self._save_as("Save KiCAD schematic", "KiCAD schematic (*.kicad_sch)")
        if not path: return
        if not path.endswith(".kicad_sch"): path += ".kicad_sch"
        from circuitforge.io import write_kicad_sch
        self._wrap(
            lambda: write_kicad_sch(self.current_canvas, netlist=self.current_netlist, path=path),
            f"Wrote KiCAD schematic to {path}")

    def _export_kicad_pcb(self):
        if not self._require_board("Export KiCAD board"): return
        path = self._save_as("Save KiCAD board", "KiCAD board (*.kicad_pcb)")
        if not path: return
        if not path.endswith(".kicad_pcb"): path += ".kicad_pcb"
        from circuitforge.io import write_kicad_pcb
        self._wrap(lambda: write_kicad_pcb(self.current_board, path=path),
                   f"Wrote KiCAD board to {path}")

    def _export_gerber(self):
        if not self._require_board("Export Gerber set"): return
        d = QtWidgets.QFileDialog.getExistingDirectory(self,
                "Choose Gerber output directory")
        if not d: return
        from circuitforge.io import write_gerber_set
        paths = self._wrap(
            lambda: write_gerber_set(self.current_board, d),
            f"Wrote Gerber set to {d}") or []
        if paths:
            QtWidgets.QMessageBox.information(
                self, "Gerber export",
                f"Wrote {len(paths)} layer file(s) to:\n{d}")

    def _export_drill(self):
        if not self._require_board("Export drill file"): return
        path = self._save_as("Save Excellon drill", "Excellon drill (*.drl);;All (*)")
        if not path: return
        from circuitforge.io import write_excellon
        self._wrap(lambda: write_excellon(self.current_board, path),
                   f"Wrote drill file to {path}")

    def _export_spice(self):
        if not self._require_netlist("Export SPICE netlist"): return
        path = self._save_as("Save SPICE netlist",
                             "SPICE deck (*.cir *.sp *.net);;All (*)")
        if not path: return
        from circuitforge.io import write_spice_deck
        self._wrap(lambda: write_spice_deck(self.current_netlist, path),
                   f"Wrote SPICE deck to {path}")

    def _export_bom(self):
        if not self._require_netlist("Export BOM"): return
        path = self._save_as("Save BOM",
                             "CSV (*.csv);;HTML (*.html);;All (*)")
        if not path: return
        from circuitforge.io import write_bom_csv, write_bom_html
        writer = write_bom_html if path.endswith(".html") else write_bom_csv
        self._wrap(lambda: writer(self.current_netlist, path),
                   f"Wrote BOM to {path}")

    def _export_svg(self):
        # Schematic SVG if a canvas is loaded; otherwise PCB SVG.
        if self.current_canvas is not None:
            path = self._save_as("Save schematic SVG", "SVG (*.svg)")
            if not path: return
            from circuitforge.io import export_schematic_svg
            self._wrap(lambda: export_schematic_svg(self.current_canvas, path),
                       f"Wrote schematic SVG to {path}")
            return
        if self.current_board is not None:
            path = self._save_as("Save board SVG", "SVG (*.svg)")
            if not path: return
            from circuitforge.io import export_pcb_svg
            self._wrap(lambda: export_pcb_svg(self.current_board, path),
                       f"Wrote board SVG to {path}")
            return
        QtWidgets.QMessageBox.information(
            self, "SVG export",
            "No schematic or board is loaded. Import one first via File → Import.")

    # ---------------- simulations ----------------
    def _open_sim_dialog(self, default):
        if not self._require_netlist(f"Simulation ({default})"): return None
        dlg = SimulationDialog(self, default=default)
        if dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec():
            return dlg.analysis, dlg.collect_params()
        return None

    def _run_simulation(self, analysis, params):
        """Dispatch + populate Scope + status bar."""
        from circuitforge.simulation import Simulator
        from circuitforge.core.units import parse_value
        sim = Simulator(self.current_netlist)

        def work():
            if analysis == "op":
                return sim.op()
            if analysis == "tran":
                return sim.tran(parse_value(params["tstop"]),
                                parse_value(params["dt"]),
                                method=params.get("method", "be"))
            if analysis == "ac":
                return sim.ac(parse_value(params["fstart"]),
                              parse_value(params["fstop"]),
                              params.get("ppd", 20))
            if analysis == "dc":
                return sim.dc(params["source"],
                              parse_value(params["start"]),
                              parse_value(params["stop"]),
                              parse_value(params["step"]))
            raise ValueError(f"unknown analysis: {analysis}")

        result = self._wrap(work, f"{analysis.upper()} analysis complete.")
        if result is None:
            return
        self.current_result = result

        if analysis == "op":
            OpPointDialog(result.operating_point, parent=self).exec_() \
                if hasattr(OpPointDialog, "exec_") else None
            return
        # transient / ac / dc → scope
        self.scope.set_result(result)
        self.tabs.setCurrentWidget(self.scope)

    def _sim_op(self):
        choice = self._open_sim_dialog("op")
        if choice: self._run_simulation(*choice)

    def _sim_dc(self):
        choice = self._open_sim_dialog("dc")
        if choice: self._run_simulation(*choice)

    def _sim_ac(self):
        choice = self._open_sim_dialog("ac")
        if choice: self._run_simulation(*choice)

    def _sim_tran(self):
        choice = self._open_sim_dialog("tran")
        if choice: self._run_simulation(*choice)

    # ---------------- PCB operations ----------------
    def _autoroute(self):
        if not self._require_board("Autoroute"): return
        from circuitforge.pcb import GridRouter
        board = self.current_board
        rats = board.ratsnest()
        if not rats:
            QtWidgets.QMessageBox.information(
                self, "Autoroute",
                "No unrouted connections in the ratsnest (the board's netlist "
                "has no pin pairs that aren't already connected by traces).")
            return
        router = GridRouter(board)
        routed = self._wrap(lambda: router.route_netlist(rats),
                            f"Autoroute finished — {len(rats)} ratsnest entries")
        if routed is None:
            return
        AutorouteDialog(len(rats), routed, parent=self).exec_()

    def _drc(self):
        if not self._require_board("DRC"): return
        from circuitforge.pcb import DRC
        drc = DRC()
        violations = self._wrap(lambda: drc.run(self.current_board),
                                f"DRC complete — {len(drc.violations)} violation(s)")
        if violations is None:
            return
        ViolationsDialog(violations, parent=self).exec_()

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

