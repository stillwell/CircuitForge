"""Parameter and result dialogs used by the Qt main window.

Each is independent and accepts a parent QWidget. They all run the work
*synchronously* — for the scale of work CircuitForge does (RC transient
in 0.1 s, AC in seconds, DRC on a small board in well under a second)
this is fine. If a future analysis grows long we can move it onto a
QThread without changing the dialog API.
"""

from ._qt import QtCore, QtGui, QtWidgets


class SimulationDialog(QtWidgets.QDialog):
    """Tabbed dialog for DC OP / DC sweep / AC / Transient parameters."""

    ANALYSES = ("op", "tran", "ac", "dc")

    def __init__(self, parent=None, default="tran"):
        super().__init__(parent)
        self.setWindowTitle("Run simulation")
        self.resize(420, 360)
        self.params = {}

        v = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        v.addWidget(self.tabs)
        self._build_op(); self._build_tran(); self._build_ac(); self._build_dc()
        self.tabs.setCurrentIndex(self.ANALYSES.index(default))

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

    @property
    def analysis(self):
        return self.ANALYSES[self.tabs.currentIndex()]

    def _build_op(self):
        tab = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(tab)
        f.addRow(QtWidgets.QLabel(
            "Computes the steady-state DC operating point (voltage at every\n"
            "node, current through every branch). No parameters."))
        self.tabs.addTab(tab, "DC operating point")

    def _build_tran(self):
        tab = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(tab)
        self.tran_tstop = QtWidgets.QLineEdit("5m"); f.addRow("Stop time", self.tran_tstop)
        self.tran_dt    = QtWidgets.QLineEdit("10u"); f.addRow("Time step", self.tran_dt)
        self.tran_method = QtWidgets.QComboBox(); self.tran_method.addItems(["be", "trap"])
        f.addRow("Method", self.tran_method)
        self.tabs.addTab(tab, "Transient")

    def _build_ac(self):
        tab = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(tab)
        self.ac_fstart = QtWidgets.QLineEdit("10");    f.addRow("Start frequency", self.ac_fstart)
        self.ac_fstop  = QtWidgets.QLineEdit("1Meg");  f.addRow("Stop frequency",  self.ac_fstop)
        self.ac_ppd    = QtWidgets.QSpinBox(); self.ac_ppd.setRange(2, 1000); self.ac_ppd.setValue(20)
        f.addRow("Points / decade", self.ac_ppd)
        self.tabs.addTab(tab, "AC sweep")

    def _build_dc(self):
        tab = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(tab)
        self.dc_source = QtWidgets.QLineEdit("V1"); f.addRow("Source ref", self.dc_source)
        self.dc_start  = QtWidgets.QLineEdit("0");  f.addRow("Start value", self.dc_start)
        self.dc_stop   = QtWidgets.QLineEdit("5");  f.addRow("Stop value",  self.dc_stop)
        self.dc_step   = QtWidgets.QLineEdit("0.1"); f.addRow("Step",       self.dc_step)
        self.tabs.addTab(tab, "DC sweep")

    def collect_params(self):
        a = self.analysis
        if a == "op":   return {}
        if a == "tran": return {"tstop": self.tran_tstop.text(),
                                "dt": self.tran_dt.text(),
                                "method": self.tran_method.currentText()}
        if a == "ac":   return {"fstart": self.ac_fstart.text(),
                                "fstop": self.ac_fstop.text(),
                                "ppd": int(self.ac_ppd.value())}
        if a == "dc":   return {"source": self.dc_source.text(),
                                "start": self.dc_start.text(),
                                "stop": self.dc_stop.text(),
                                "step": self.dc_step.text()}
        return {}


class OpPointDialog(QtWidgets.QDialog):
    """Display a DC operating point as a sortable table."""

    def __init__(self, op_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DC operating point")
        self.resize(360, 480)
        v = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(len(op_dict), 2)
        self.table.setHorizontalHeaderLabels(["Net", "Voltage (V)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        for i, (net, v_) in enumerate(sorted(op_dict.items())):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(net))
            item = QtWidgets.QTableWidgetItem(f"{v_:.6g}")
            item.setData(QtCore.Qt.UserRole, float(v_))
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(i, 1, item)
        v.addWidget(self.table, 1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        bb.rejected.connect(self.reject); bb.accepted.connect(self.accept)
        v.addWidget(bb)


class ViolationsDialog(QtWidgets.QDialog):
    """Render a list of DRC violations in a table."""

    def __init__(self, violations, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"DRC — {len(violations)} violation(s)")
        self.resize(720, 360)
        v = QtWidgets.QVBoxLayout(self)
        if not violations:
            v.addWidget(QtWidgets.QLabel("✅ No DRC violations."))
        else:
            self.table = QtWidgets.QTableWidget(len(violations), 4)
            self.table.setHorizontalHeaderLabels(
                ["Severity", "Rule", "Message", "Location"])
            self.table.verticalHeader().setVisible(False)
            self.table.horizontalHeader().setStretchLastSection(True)
            for i, vi in enumerate(violations):
                self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(vi.severity))
                self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(vi.rule))
                self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(vi.message))
                self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(
                    f"{vi.location}" if vi.location else ""))
            v.addWidget(self.table, 1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        bb.rejected.connect(self.reject); bb.accepted.connect(self.accept)
        v.addWidget(bb)


class AutorouteDialog(QtWidgets.QDialog):
    """Summarise autoroute results."""

    def __init__(self, ratsnest_count, routed, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autoroute results")
        self.resize(360, 200)
        v = QtWidgets.QVBoxLayout(self)
        ok = len(routed)
        fail = max(0, ratsnest_count - ok)
        msg = QtWidgets.QLabel(
            f"<h3>Lee's algorithm autorouter</h3>"
            f"<p><b>{ratsnest_count}</b> unrouted connections in the ratsnest.<br>"
            f"<b style='color:#0d8'>{ok}</b> routed successfully.<br>"
            f"<b style='color:#d04'>{fail}</b> failed (no path found).</p>")
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setWordWrap(True)
        v.addWidget(msg)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        bb.rejected.connect(self.reject); bb.accepted.connect(self.accept)
        v.addWidget(bb)
