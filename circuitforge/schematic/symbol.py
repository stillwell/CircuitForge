"""Schematic symbols — geometric primitives that render a component on the canvas.

Symbols are GUI-agnostic. They produce a list of drawing instructions (lines,
arcs, rects, text) that a Qt/svg/cairo backend can render. The same data
serializes to SVG for documentation export.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional


@dataclass
class SymbolPrimitive:
    kind: str                                # 'line', 'rect', 'arc', 'circle', 'text', 'polyline'
    points: List[Tuple[float, float]] = field(default_factory=list)
    text: str = ""
    radius: float = 0.0
    width: float = 0.5

    def to_svg(self):
        if self.kind == "line" and len(self.points) >= 2:
            x1, y1 = self.points[0]; x2, y2 = self.points[1]
            return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                    f'stroke="black" stroke-width="{self.width}"/>')
        if self.kind == "rect" and len(self.points) >= 2:
            x1, y1 = self.points[0]; x2, y2 = self.points[1]
            w = x2 - x1; h = y2 - y1
            return (f'<rect x="{x1}" y="{y1}" width="{w}" height="{h}" '
                    f'fill="none" stroke="black" stroke-width="{self.width}"/>')
        if self.kind == "circle" and self.points:
            cx, cy = self.points[0]
            return (f'<circle cx="{cx}" cy="{cy}" r="{self.radius}" '
                    f'fill="none" stroke="black" stroke-width="{self.width}"/>')
        if self.kind == "text" and self.points:
            x, y = self.points[0]
            return f'<text x="{x}" y="{y}" font-size="3">{self.text}</text>'
        if self.kind == "polyline" and self.points:
            pts = " ".join(f"{x},{y}" for x, y in self.points)
            return (f'<polyline points="{pts}" fill="none" stroke="black" '
                    f'stroke-width="{self.width}"/>')
        return ""


@dataclass
class Symbol:
    name: str
    primitives: List[SymbolPrimitive] = field(default_factory=list)
    pin_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    bbox: Tuple[float, float, float, float] = (-5, -5, 5, 5)

    def to_svg(self):
        body = "\n".join(p.to_svg() for p in self.primitives)
        x0, y0, x1, y1 = self.bbox
        return (f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'viewBox="{x0} {y0} {x1 - x0} {y1 - y0}">\n{body}\n</svg>')


# ------------- prebuilt symbol catalog ------------------------------------

class GenericSymbols:
    """Factory of common schematic-symbol geometries (KiCAD-ish)."""

    @staticmethod
    def resistor() -> Symbol:
        # zig-zag resistor
        prims = [
            SymbolPrimitive(kind="line", points=[(-10, 0), (-6, 0)]),
            SymbolPrimitive(kind="polyline", points=[
                (-6, 0), (-5, -2), (-3, 2), (-1, -2), (1, 2), (3, -2), (5, 2), (6, 0)]),
            SymbolPrimitive(kind="line", points=[(6, 0), (10, 0)]),
        ]
        return Symbol(name="R", primitives=prims,
                      pin_positions={"1": (-10, 0), "2": (10, 0)},
                      bbox=(-12, -4, 12, 4))

    @staticmethod
    def capacitor() -> Symbol:
        prims = [
            SymbolPrimitive(kind="line", points=[(-10, 0), (-1, 0)]),
            SymbolPrimitive(kind="line", points=[(-1, -4), (-1, 4)]),
            SymbolPrimitive(kind="line", points=[(1, -4), (1, 4)]),
            SymbolPrimitive(kind="line", points=[(1, 0), (10, 0)]),
        ]
        return Symbol(name="C", primitives=prims,
                      pin_positions={"1": (-10, 0), "2": (10, 0)},
                      bbox=(-12, -5, 12, 5))

    @staticmethod
    def inductor() -> Symbol:
        prims = [
            SymbolPrimitive(kind="line", points=[(-10, 0), (-6, 0)]),
            SymbolPrimitive(kind="arc", points=[(-4, 0)], radius=2),
            SymbolPrimitive(kind="arc", points=[(0, 0)], radius=2),
            SymbolPrimitive(kind="arc", points=[(4, 0)], radius=2),
            SymbolPrimitive(kind="line", points=[(6, 0), (10, 0)]),
        ]
        return Symbol(name="L", primitives=prims,
                      pin_positions={"1": (-10, 0), "2": (10, 0)},
                      bbox=(-12, -4, 12, 4))

    @staticmethod
    def diode() -> Symbol:
        prims = [
            SymbolPrimitive(kind="line", points=[(-10, 0), (-3, 0)]),
            SymbolPrimitive(kind="polyline", points=[(-3, -4), (3, 0), (-3, 4), (-3, -4)]),
            SymbolPrimitive(kind="line", points=[(3, -4), (3, 4)]),
            SymbolPrimitive(kind="line", points=[(3, 0), (10, 0)]),
        ]
        return Symbol(name="D", primitives=prims,
                      pin_positions={"A": (-10, 0), "K": (10, 0)},
                      bbox=(-12, -5, 12, 5))

    @staticmethod
    def voltage_source() -> Symbol:
        prims = [
            SymbolPrimitive(kind="circle", points=[(0, 0)], radius=6),
            SymbolPrimitive(kind="text", points=[(-2, -2)], text="+"),
            SymbolPrimitive(kind="text", points=[(-2, 5)], text="-"),
            SymbolPrimitive(kind="line", points=[(0, -10), (0, -6)]),
            SymbolPrimitive(kind="line", points=[(0, 6), (0, 10)]),
        ]
        return Symbol(name="V", primitives=prims,
                      pin_positions={"+": (0, -10), "-": (0, 10)},
                      bbox=(-8, -12, 8, 12))

    @staticmethod
    def ground() -> Symbol:
        prims = [
            SymbolPrimitive(kind="line", points=[(0, -5), (0, 0)]),
            SymbolPrimitive(kind="line", points=[(-6, 0), (6, 0)]),
            SymbolPrimitive(kind="line", points=[(-4, 2), (4, 2)]),
            SymbolPrimitive(kind="line", points=[(-2, 4), (2, 4)]),
        ]
        return Symbol(name="GND", primitives=prims,
                      pin_positions={"1": (0, -5)},
                      bbox=(-7, -6, 7, 5))

    @staticmethod
    def opamp() -> Symbol:
        prims = [
            SymbolPrimitive(kind="polyline", points=[(-10, -10), (10, 0), (-10, 10), (-10, -10)]),
            SymbolPrimitive(kind="text", points=[(-8, -4)], text="+"),
            SymbolPrimitive(kind="text", points=[(-8, 6)], text="-"),
            SymbolPrimitive(kind="line", points=[(-15, -6), (-10, -6)]),
            SymbolPrimitive(kind="line", points=[(-15, 6), (-10, 6)]),
            SymbolPrimitive(kind="line", points=[(10, 0), (15, 0)]),
        ]
        return Symbol(name="OPAMP",
                      primitives=prims,
                      pin_positions={"IN+": (-15, -6), "IN-": (-15, 6), "OUT": (15, 0)},
                      bbox=(-16, -12, 16, 12))


class SymbolLibrary:
    """Maps component type names to Symbol instances."""

    def __init__(self):
        self.symbols: Dict[str, Symbol] = {}
        self._load_builtin()

    def _load_builtin(self):
        self.symbols["Resistor"]      = GenericSymbols.resistor()
        self.symbols["Capacitor"]     = GenericSymbols.capacitor()
        self.symbols["Inductor"]      = GenericSymbols.inductor()
        self.symbols["Diode"]         = GenericSymbols.diode()
        self.symbols["VoltageSource"] = GenericSymbols.voltage_source()
        self.symbols["GND"]           = GenericSymbols.ground()
        self.symbols["IdealOpAmp"]    = GenericSymbols.opamp()

    def lookup(self, type_name) -> Optional[Symbol]:
        return self.symbols.get(type_name)

    def register(self, type_name, symbol):
        self.symbols[type_name] = symbol
