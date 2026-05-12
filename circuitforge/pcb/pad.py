"""Pads — copper landing pads for component pins."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class PadShape(Enum):
    CIRCLE = "circle"
    RECT = "rect"
    OVAL = "oval"
    ROUNDED = "rounded"
    TRAPEZOID = "trapezoid"


@dataclass
class Pad:
    """A copper pad with optional plated drill hole."""
    name: str                      # pad number / name (e.g. "1", "GND")
    x: float = 0.0
    y: float = 0.0
    width: float = 1.5             # mm
    height: float = 1.5
    shape: PadShape = PadShape.CIRCLE
    drill_diameter: float = 0.0    # 0 = SMD, >0 = through-hole
    layer: str = "F.Cu"
    rotation: float = 0.0
    net: Optional[str] = None
    solder_mask_margin: float = 0.05
    solder_paste_margin: float = 0.0

    @property
    def is_through_hole(self):
        return self.drill_diameter > 0.0

    def bbox(self):
        hw = self.width / 2; hh = self.height / 2
        return (self.x - hw, self.y - hh, self.x + hw, self.y + hh)
