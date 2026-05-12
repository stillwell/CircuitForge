"""Copper traces on the PCB."""

from dataclasses import dataclass, field
from typing import Tuple, List, Optional


@dataclass
class Segment:
    x1: float; y1: float
    x2: float; y2: float
    width: float = 0.25      # mm
    layer: str = "F.Cu"
    net: Optional[str] = None

    def length(self):
        return ((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2) ** 0.5

    def bbox(self):
        return (min(self.x1, self.x2), min(self.y1, self.y2),
                max(self.x1, self.x2), max(self.y1, self.y2))


@dataclass
class Trace:
    net: str
    segments: List[Segment] = field(default_factory=list)
    width: float = 0.25
    layer: str = "F.Cu"

    def add_segment(self, x1, y1, x2, y2, layer=None, width=None):
        s = Segment(x1, y1, x2, y2,
                    width=width or self.width,
                    layer=layer or self.layer,
                    net=self.net)
        self.segments.append(s)
        return s

    def total_length(self):
        return sum(s.length() for s in self.segments)
