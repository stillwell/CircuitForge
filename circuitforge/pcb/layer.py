"""PCB layer system.

Inspired by KiCAD's layer model. Each layer has a type (copper, silkscreen,
mask, paste, drawing, mechanical) and a side (top, bottom, inner, both).
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Layer:
    name: str
    type_: str        # 'copper', 'silk', 'mask', 'paste', 'drawing', 'mechanical', 'edge'
    side: str         # 'top', 'bottom', 'inner', 'both'
    number: int = 0
    color: str = "#888888"
    enabled: bool = True


def _build_default_stack(copper_layers=2) -> List[Layer]:
    layers: List[Layer] = []
    # Top side
    layers.append(Layer("F.Cu",     "copper", "top",    number=0,  color="#C83232"))
    layers.append(Layer("F.Paste",  "paste",  "top",    number=1,  color="#A0A0A0"))
    layers.append(Layer("F.Mask",   "mask",   "top",    number=2,  color="#660066"))
    layers.append(Layer("F.SilkS",  "silk",   "top",    number=3,  color="#F0F0F0"))
    # Inner copper layers
    for i in range(1, copper_layers - 1):
        layers.append(Layer(f"In{i}.Cu", "copper", "inner", number=10 + i,
                            color="#7F7F7F"))
    # Bottom side
    layers.append(Layer("B.Cu",     "copper", "bottom", number=31, color="#3232C8"))
    layers.append(Layer("B.SilkS",  "silk",   "bottom", number=32, color="#F0F0F0"))
    layers.append(Layer("B.Mask",   "mask",   "bottom", number=33, color="#660066"))
    layers.append(Layer("B.Paste",  "paste",  "bottom", number=34, color="#A0A0A0"))
    # Drawing / mechanical
    layers.append(Layer("Edge.Cuts", "edge",   "both", number=44, color="#FFFF00"))
    layers.append(Layer("Margin",    "drawing","both", number=45, color="#FFAA00"))
    layers.append(Layer("Dwgs.User", "drawing","both", number=46, color="#88FFFF"))
    layers.append(Layer("Cmts.User", "drawing","both", number=47, color="#88FFFF"))
    layers.append(Layer("F.Fab",     "drawing","top",  number=49, color="#888888"))
    layers.append(Layer("B.Fab",     "drawing","bottom",number=48,color="#888888"))
    return layers


STANDARD_LAYERS = _build_default_stack(copper_layers=2)


class LayerStack:
    """Configurable layer stack for a board."""

    def __init__(self, copper_layers=2):
        self.copper_layers = copper_layers
        self.layers: List[Layer] = _build_default_stack(copper_layers)

    def copper(self) -> List[Layer]:
        return [l for l in self.layers if l.type_ == "copper"]

    def by_name(self, name) -> Layer:
        for l in self.layers:
            if l.name == name:
                return l
        raise KeyError(f"no layer named {name!r}")

    def enabled(self) -> List[Layer]:
        return [l for l in self.layers if l.enabled]

    def __iter__(self):
        return iter(self.layers)

    def __len__(self):
        return len(self.layers)
