"""Wires and orthogonal wire routing.

A Wire is a polyline (list of grid-aligned points) connecting two endpoints
that ultimately get merged into a single Node in the netlist.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


Point = Tuple[float, float]


@dataclass
class Wire:
    points: List[Point] = field(default_factory=list)
    net_name: Optional[str] = None

    def add(self, x, y):
        self.points.append((x, y))

    def length(self):
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:]):
            total += abs(x2 - x1) + abs(y2 - y1)
        return total

    def to_svg(self):
        pts = " ".join(f"{x},{y}" for x, y in self.points)
        return (f'<polyline points="{pts}" stroke="green" stroke-width="0.5" '
                f'fill="none"/>')


class WireRouter:
    """Orthogonal (Manhattan) wire router with simple L-shape routing."""

    GRID = 2.54  # 0.1 inch — classic schematic grid

    def snap(self, p):
        return (round(p[0] / self.GRID) * self.GRID,
                round(p[1] / self.GRID) * self.GRID)

    def route_l(self, start: Point, end: Point, horizontal_first=True) -> Wire:
        s = self.snap(start); e = self.snap(end)
        if horizontal_first:
            mid = (e[0], s[1])
        else:
            mid = (s[0], e[1])
        w = Wire(points=[s, mid, e])
        # collapse colinear points
        if w.points[0] == w.points[1]:
            w.points = w.points[1:]
        if w.points[-2] == w.points[-1]:
            w.points = w.points[:-1]
        return w

    def route_z(self, start: Point, end: Point) -> Wire:
        """Z-shaped routing (two corners) — used when an L can't fit."""
        s = self.snap(start); e = self.snap(end)
        midx = (s[0] + e[0]) / 2
        return Wire(points=[s, (midx, s[1]), (midx, e[1]), e])
