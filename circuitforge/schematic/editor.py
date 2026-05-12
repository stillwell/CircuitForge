"""Schematic editor — Qt widget wrapping a SchematicCanvas.

The editor is optional and only activates when PyQt5 or PySide6 is installed.
A headless `SchematicEditorModel` is always available for scripted use.
"""

from .canvas import SchematicCanvas


class SchematicEditorModel:
    """Pure-data backend that GUI binds to."""

    def __init__(self, netlist=None):
        from circuitforge.core.netlist import Netlist
        self.netlist = netlist or Netlist()
        self.canvas = SchematicCanvas()
        self.history = []     # for undo
        self.future = []      # for redo
        self.selection = set()

    def add_component(self, component, x, y, rotation=0):
        self.netlist.add(component)
        self.canvas.place(component, x, y, rotation)
        self._snapshot()

    def connect(self, ref_a, pin_a, ref_b, pin_b, net_name=None):
        a = self.netlist.get(ref_a); b = self.netlist.get(ref_b)
        if a is None or b is None:
            raise KeyError("component not in netlist")
        net_name = net_name or f"N{len(self.netlist._nodes) + 1}"
        a.get_pin(pin_a).net = net_name
        b.get_pin(pin_b).net = net_name
        self.netlist.node(net_name).pins.extend([(ref_a, pin_a), (ref_b, pin_b)])
        pa = self.canvas.get_placement(ref_a)
        pb = self.canvas.get_placement(ref_b)
        if pa and pb:
            self.canvas.connect((pa.x, pa.y), (pb.x, pb.y), net_name)
        self._snapshot()

    def _snapshot(self):
        # Lightweight history for undo (placements + nets only)
        snap = ([(p.component_ref, p.x, p.y, p.rotation) for p in self.canvas.placements],
                [(w.points[:], w.net_name) for w in self.canvas.wires])
        self.history.append(snap)
        self.future.clear()

    def undo(self):
        if len(self.history) > 1:
            self.future.append(self.history.pop())

    def redo(self):
        if self.future:
            self.history.append(self.future.pop())


# ---- Optional Qt widget --------------------------------------------------

class SchematicEditor:
    """Qt-based schematic editor. Created only when PyQt is available."""

    def __init__(self, model=None):
        try:
            from PyQt5 import QtWidgets, QtCore, QtGui
            self._qt = (QtWidgets, QtCore, QtGui)
        except ImportError:
            try:
                from PySide6 import QtWidgets, QtCore, QtGui
                self._qt = (QtWidgets, QtCore, QtGui)
            except ImportError:
                self._qt = None
        self.model = model or SchematicEditorModel()
        self._widget = None

    @property
    def widget(self):
        if self._qt is None:
            raise RuntimeError("Neither PyQt5 nor PySide6 is installed.")
        if self._widget is None:
            QtWidgets, QtCore, QtGui = self._qt
            self._widget = _SchematicView(self.model, QtWidgets, QtCore, QtGui)
        return self._widget


def _SchematicView(model, QtWidgets, QtCore, QtGui):
    """Construct the QGraphicsView/Scene wrapping the schematic canvas."""
    scene = QtWidgets.QGraphicsScene()
    scene.setBackgroundBrush(QtGui.QColor(255, 255, 245))

    # draw grid lines (light grey)
    bbox = model.canvas.bounding_box()
    pen = QtGui.QPen(QtGui.QColor(220, 220, 220)); pen.setWidthF(0.1)
    for x in range(int(bbox[0]) - 50, int(bbox[2]) + 50, int(model.canvas.GRID)):
        scene.addLine(x, bbox[1] - 50, x, bbox[3] + 50, pen)
    for y in range(int(bbox[1]) - 50, int(bbox[3]) + 50, int(model.canvas.GRID)):
        scene.addLine(bbox[0] - 50, y, bbox[2] + 50, y, pen)

    # draw symbols
    for p in model.canvas.placements:
        sym = model.canvas.symbol_library.lookup(p.type_name)
        if sym is None:
            continue
        group = QtWidgets.QGraphicsItemGroup()
        pen = QtGui.QPen(QtCore.Qt.black); pen.setWidthF(0.4)
        for prim in sym.primitives:
            if prim.kind == "line" and len(prim.points) >= 2:
                (x1, y1), (x2, y2) = prim.points[:2]
                group.addToGroup(scene.addLine(x1, y1, x2, y2, pen))
            elif prim.kind == "rect" and len(prim.points) >= 2:
                (x1, y1), (x2, y2) = prim.points[:2]
                group.addToGroup(scene.addRect(x1, y1, x2 - x1, y2 - y1, pen))
            elif prim.kind == "circle" and prim.points:
                cx, cy = prim.points[0]
                group.addToGroup(scene.addEllipse(cx - prim.radius, cy - prim.radius,
                                                  2 * prim.radius, 2 * prim.radius, pen))
            elif prim.kind == "polyline":
                for (x1, y1), (x2, y2) in zip(prim.points, prim.points[1:]):
                    group.addToGroup(scene.addLine(x1, y1, x2, y2, pen))
            elif prim.kind == "text" and prim.points:
                x, y = prim.points[0]
                ti = scene.addText(prim.text)
                ti.setPos(x, y)
                group.addToGroup(ti)
        group.setPos(p.x, p.y); group.setRotation(p.rotation)
        # reference designator label
        label = scene.addText(p.component_ref)
        label.setPos(p.x - 5, p.y - 14)

    # draw wires
    wire_pen = QtGui.QPen(QtGui.QColor(20, 120, 20)); wire_pen.setWidthF(0.4)
    for w in model.canvas.wires:
        for (x1, y1), (x2, y2) in zip(w.points, w.points[1:]):
            scene.addLine(x1, y1, x2, y2, wire_pen)

    view = QtWidgets.QGraphicsView(scene)
    view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
    view.scale(4, 4)
    return view
