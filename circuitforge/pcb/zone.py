"""Copper pour zones (ground planes, polygon pours)."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class Zone:
    net: str = "GND"
    layer: str = "F.Cu"
    polygon: List[Tuple[float, float]] = field(default_factory=list)
    clearance: float = 0.2
    min_thickness: float = 0.25
    fill_mode: str = "solid"       # 'solid' | 'hatched' | 'none'
    keep_islands: bool = False
    thermal_relief_gap: float = 0.5
    thermal_relief_spoke_width: float = 0.5
