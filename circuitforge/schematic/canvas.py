"""Headless schematic canvas — owns placed components, wires, and labels.

The Qt GUI wraps this with a QGraphicsView; the canvas itself is just data
plus geometry queries.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from .symbol import SymbolLibrary
from .wire import Wire, WireRouter


@dataclass
class PlacedSymbol:
    component_ref: str
    type_name: str
    x: float
    y: float
    rotation: int = 0
    mirror: bool = False


@dataclass
class NetLabel:
    name: str
    x: float
    y: float
    rotation: int = 0


class SchematicCanvas:
    GRID = 2.54
    SHEET_W = 297.0    # A4 mm
    SHEET_H = 210.0

    def __init__(self):
        self.placements: List[PlacedSymbol] = []
        self.wires: List[Wire] = []
        self.labels: List[NetLabel] = []
        self.symbol_library = SymbolLibrary()
        self.router = WireRouter()

    # ----- placement -----
    def place(self, component, x, y, rotation=0):
        type_name = type(component).__name__
        self.placements.append(PlacedSymbol(
            component_ref=component.ref, type_name=type_name,
            x=self._snap(x), y=self._snap(y), rotation=rotation))
        component.x = x; component.y = y; component.rotation = rotation

    def get_placement(self, ref):
        for p in self.placements:
            if p.component_ref == ref:
                return p
        return None

    # ----- wiring -----
    def connect(self, start, end, net_name=None):
        w = self.router.route_l(start, end)
        w.net_name = net_name
        self.wires.append(w)
        return w

    def add_label(self, net_name, x, y):
        self.labels.append(NetLabel(name=net_name, x=self._snap(x), y=self._snap(y)))

    # ----- geometry -----
    def _snap(self, v):
        return round(v / self.GRID) * self.GRID

    def bounding_box(self):
        if not self.placements and not self.wires:
            return (0, 0, self.SHEET_W, self.SHEET_H)
        xs, ys = [], []
        for p in self.placements:
            xs += [p.x - 10, p.x + 10]; ys += [p.y - 10, p.y + 10]
        for w in self.wires:
            for x, y in w.points:
                xs.append(x); ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys))

    # ----- export -----
    def to_svg(self):
        x0, y0, x1, y1 = self.bounding_box()
        margin = 10
        w = (x1 - x0) + 2 * margin
        h = (y1 - y0) + 2 * margin
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" '
               f'viewBox="{x0 - margin} {y0 - margin} {w} {h}" '
               f'width="{w * 4}" height="{h * 4}">']
        # symbols
        for p in self.placements:
            sym = self.symbol_library.lookup(p.type_name)
            if sym is None:
                continue
            out.append(f'<g transform="translate({p.x},{p.y}) rotate({p.rotation})">')
            for prim in sym.primitives:
                out.append(prim.to_svg())
            out.append(f'<text x="0" y="-12" font-size="3" '
                       f'text-anchor="middle">{p.component_ref}</text>')
            out.append('</g>')
        # wires
        for w in self.wires:
            out.append(w.to_svg())
        # labels
        for lbl in self.labels:
            out.append(f'<text x="{lbl.x}" y="{lbl.y}" font-size="3" '
                       f'fill="blue">{lbl.name}</text>')
        out.append("</svg>")
        return "\n".join(out)
