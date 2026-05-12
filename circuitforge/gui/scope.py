"""Oscilloscope / waveform viewer for simulation results."""

from ._qt import QtCore, QtGui, QtWidgets


class Scope(QtWidgets.QWidget):
    """Displays SimulationResult traces. Uses matplotlib if available, else QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result = None
        self._selected_nets = []
        layout = QtWidgets.QVBoxLayout(self)

        toolbar = QtWidgets.QHBoxLayout()
        self.net_box = QtWidgets.QComboBox()
        self.net_box.setEditable(False)
        toolbar.addWidget(QtWidgets.QLabel("Trace:"))
        toolbar.addWidget(self.net_box, 1)
        layout.addLayout(toolbar)

        try:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            self.fig = Figure(figsize=(8, 4))
            self.canvas = FigureCanvas(self.fig)
            self.ax = self.fig.add_subplot(111)
            layout.addWidget(self.canvas)
            self._mpl = True
        except ImportError:
            self.canvas = _SimpleCanvas(self)
            layout.addWidget(self.canvas)
            self._mpl = False

        self.net_box.currentTextChanged.connect(self._redraw)

    def set_result(self, result):
        self.result = result
        self.net_box.clear()
        if result is None or not result.waveforms:
            return
        for name in sorted(result.waveforms):
            self.net_box.addItem(name)

    def _redraw(self, net):
        if self.result is None or net not in self.result.waveforms:
            return
        ind = self.result.independent
        wave = self.result.waveforms[net]
        if self._mpl:
            self.ax.clear()
            label = f"V({net})"
            if self.result.analysis == "ac":
                # plot magnitude in dB
                import numpy as np
                mag_db = 20 * np.log10(np.maximum(np.abs(wave), 1e-12))
                self.ax.semilogx(ind, mag_db)
                self.ax.set_xlabel("Frequency (Hz)")
                self.ax.set_ylabel("Magnitude (dB)")
            else:
                self.ax.plot(ind, getattr(wave, "real", wave))
                self.ax.set_xlabel("Time (s)" if self.result.analysis == "tran"
                                   else "Sweep")
                self.ax.set_ylabel(label)
            self.ax.grid(True, alpha=0.3)
            self.fig.tight_layout()
            self.canvas.draw()
        else:
            self.canvas.set_trace(ind, [getattr(v, "real", v) for v in wave])


class _SimpleCanvas(QtWidgets.QWidget):
    """Fallback Qt-only plotter when matplotlib is unavailable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.x = []
        self.y = []
        self.setMinimumSize(400, 200)

    def set_trace(self, xs, ys):
        self.x = list(xs); self.y = list(ys)
        self.update()

    def paintEvent(self, event):
        from ._qt import QtGui, QtCore
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtCore.Qt.black)
        if not self.x:
            return
        w = self.width(); h = self.height()
        xmin, xmax = min(self.x), max(self.x)
        ymin, ymax = min(self.y), max(self.y)
        if xmax == xmin: xmax = xmin + 1
        if ymax == ymin: ymax = ymin + 1
        pen = QtGui.QPen(QtCore.Qt.green); pen.setWidth(1)
        p.setPen(pen)
        pts = []
        for x, y in zip(self.x, self.y):
            sx = (x - xmin) / (xmax - xmin) * (w - 20) + 10
            sy = h - 10 - (y - ymin) / (ymax - ymin) * (h - 20)
            pts.append(QtCore.QPointF(sx, sy))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])
