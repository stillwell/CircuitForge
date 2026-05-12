"""Vias — plated through-holes connecting layers."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Via:
    x: float = 0.0
    y: float = 0.0
    drill: float = 0.3       # mm — drill diameter
    diameter: float = 0.6    # mm — pad/annular ring diameter
    layer_from: str = "F.Cu"
    layer_to: str = "B.Cu"
    net: Optional[str] = None
    type_: str = "through"    # 'through', 'blind', 'buried', 'micro'
