"""Footprints — physical landing patterns for components on a PCB."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .pad import Pad, PadShape


@dataclass
class Footprint:
    name: str
    description: str = ""
    pads: List[Pad] = field(default_factory=list)
    courtyard_w: float = 0.0
    courtyard_h: float = 0.0
    silk_lines: List = field(default_factory=list)
    attribute: str = "smd"        # 'smd', 'tht', 'mixed', 'virtual'
    layer: str = "F.Cu"

    def get_pad(self, name):
        for p in self.pads:
            if p.name == name:
                return p
        return None


def _smd_two_pad(name, w, h, pitch):
    fp = Footprint(name=name, description=f"SMD two-pad {name}",
                   courtyard_w=pitch + w + 0.5, courtyard_h=h + 0.5,
                   attribute="smd")
    fp.pads.append(Pad("1", x=-pitch / 2, width=w, height=h, shape=PadShape.RECT))
    fp.pads.append(Pad("2", x=+pitch / 2, width=w, height=h, shape=PadShape.RECT))
    return fp


def _dip(name, n, row_pitch=7.62, pin_pitch=2.54):
    fp = Footprint(name=name, description=f"DIP-{n} through-hole",
                   attribute="tht")
    per_row = n // 2
    for i in range(per_row):
        x = i * pin_pitch - (per_row - 1) * pin_pitch / 2
        fp.pads.append(Pad(str(i + 1), x=x, y=-row_pitch / 2,
                           width=1.6, height=1.6, shape=PadShape.OVAL,
                           drill_diameter=0.8, layer="*.Cu"))
        fp.pads.append(Pad(str(n - i), x=x, y=+row_pitch / 2,
                           width=1.6, height=1.6, shape=PadShape.OVAL,
                           drill_diameter=0.8, layer="*.Cu"))
    fp.courtyard_w = (per_row * pin_pitch) + 2.0
    fp.courtyard_h = row_pitch + 1.0
    return fp


def _soic(name, n, body_w=3.9, pitch=1.27, pad_w=1.5, pad_h=0.6):
    fp = Footprint(name=name, description=f"SOIC-{n}", attribute="smd")
    per_row = n // 2
    for i in range(per_row):
        y = i * pitch - (per_row - 1) * pitch / 2
        fp.pads.append(Pad(str(i + 1),
                           x=-body_w / 2 - pad_w / 2, y=y,
                           width=pad_w, height=pad_h, shape=PadShape.RECT))
        fp.pads.append(Pad(str(n - i),
                           x=+body_w / 2 + pad_w / 2, y=y,
                           width=pad_w, height=pad_h, shape=PadShape.RECT))
    fp.courtyard_w = body_w + 2 * pad_w + 1
    fp.courtyard_h = (per_row - 1) * pitch + pad_h + 1
    return fp


def _qfp(name, n, body=10.0, pitch=0.5, pad_w=1.5, pad_h=0.3):
    """Quad flat package, n leads (multiple of 4)."""
    fp = Footprint(name=name, description=f"QFP-{n}", attribute="smd")
    per_side = n // 4
    span = (per_side - 1) * pitch
    half = body / 2 + pad_w / 2
    # bottom side (pins 1..per_side, going right)
    for i in range(per_side):
        x = -span / 2 + i * pitch
        fp.pads.append(Pad(str(i + 1), x=x, y=half,
                           width=pad_h, height=pad_w, shape=PadShape.RECT))
    # right side
    for i in range(per_side):
        y = span / 2 - i * pitch
        fp.pads.append(Pad(str(per_side + i + 1), x=half, y=y,
                           width=pad_w, height=pad_h, shape=PadShape.RECT))
    # top side
    for i in range(per_side):
        x = span / 2 - i * pitch
        fp.pads.append(Pad(str(2 * per_side + i + 1), x=x, y=-half,
                           width=pad_h, height=pad_w, shape=PadShape.RECT))
    # left side
    for i in range(per_side):
        y = -span / 2 + i * pitch
        fp.pads.append(Pad(str(3 * per_side + i + 1), x=-half, y=y,
                           width=pad_w, height=pad_h, shape=PadShape.RECT))
    fp.courtyard_w = body + 2 * pad_w + 1
    fp.courtyard_h = fp.courtyard_w
    return fp


class FootprintLibrary:
    """Mutable library of footprints."""

    def __init__(self):
        self.footprints: Dict[str, Footprint] = {}
        self._load_default()

    def _load_default(self):
        # SMD two-terminal: resistors & non-polar caps
        for size, dims in {
            "R_0402": (0.5, 0.55, 0.55),
            "R_0603": (0.85, 0.95, 0.85),
            "R_0805": (1.05, 1.15, 1.05),
            "R_1206": (1.6, 1.7, 1.95),
            "C_0402": (0.5, 0.55, 0.55),
            "C_0603": (0.85, 0.95, 0.85),
            "C_0805": (1.05, 1.15, 1.05),
            "C_1206": (1.6, 1.7, 1.95),
            "L_0805": (1.05, 1.15, 1.05),
        }.items():
            self.register(_smd_two_pad(size, *dims))

        for n in (4, 6, 8, 14, 16, 18, 20, 24, 28, 40):
            self.register(_dip(f"DIP-{n}", n))

        for n in (8, 14, 16, 20, 24, 28):
            self.register(_soic(f"SOIC-{n}", n))

        for n in (32, 44, 48, 64, 100, 144):
            self.register(_qfp(f"LQFP-{n}", n))

        # TO-92, TO-220
        fp = Footprint(name="TO-92", attribute="tht")
        for i, x in enumerate([-1.27, 0, 1.27]):
            fp.pads.append(Pad(str(i + 1), x=x, y=0, width=1.6, height=1.6,
                               shape=PadShape.OVAL, drill_diameter=0.8,
                               layer="*.Cu"))
        fp.courtyard_w = 5; fp.courtyard_h = 3
        self.register(fp)

        fp = Footprint(name="TO-220", attribute="tht")
        for i, x in enumerate([-2.54, 0, 2.54]):
            fp.pads.append(Pad(str(i + 1), x=x, y=0, width=2.5, height=2.5,
                               shape=PadShape.OVAL, drill_diameter=1.2,
                               layer="*.Cu"))
        fp.courtyard_w = 10.5; fp.courtyard_h = 4.5
        self.register(fp)

        # SOT-23
        fp = Footprint(name="SOT-23", attribute="smd")
        for i, (px, py) in enumerate([(-0.95, -0.95), (-0.95, 0.95), (0.95, 0)]):
            fp.pads.append(Pad(str(i + 1), x=px, y=py, width=0.6, height=0.9,
                               shape=PadShape.RECT))
        fp.courtyard_w = 3.0; fp.courtyard_h = 2.5
        self.register(fp)

    def register(self, fp):
        self.footprints[fp.name] = fp

    def get(self, name) -> Optional[Footprint]:
        return self.footprints.get(name)

    def __iter__(self):
        return iter(self.footprints.values())

    def __len__(self):
        return len(self.footprints)
