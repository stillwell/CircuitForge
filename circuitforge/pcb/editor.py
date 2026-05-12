"""Board — top-level PCB container holding placements, traces, vias, zones."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from .layer import LayerStack
from .footprint import Footprint, FootprintLibrary
from .trace import Trace, Segment
from .via import Via
from .zone import Zone
from .pad import Pad


@dataclass
class Placement:
    """An instance of a footprint placed on the board."""
    ref: str
    footprint: Footprint
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    side: str = "top"            # 'top' | 'bottom'
    value: str = ""

    def pad_position(self, pad_name):
        p = self.footprint.get_pad(pad_name)
        if p is None:
            raise KeyError(f"pad {pad_name} not in footprint {self.footprint.name}")
        return (self.x + p.x, self.y + p.y)


class Board:
    """A PCB."""

    def __init__(self, width=100.0, height=80.0, copper_layers=2):
        self.width = width
        self.height = height
        self.layers = LayerStack(copper_layers)
        self.footprint_library = FootprintLibrary()
        self.placements: List[Placement] = []
        self.traces: List[Trace] = []
        self.vias: List[Via] = []
        self.zones: List[Zone] = []
        self.outline: List[Tuple[float, float]] = [
            (0, 0), (width, 0), (width, height), (0, height), (0, 0)
        ]
        self.netlist = None        # link back to source Netlist
        self.title = "Untitled"
        self.rules = None          # DRCRule

    def place(self, ref, footprint_name, x, y, rotation=0, side="top", value=""):
        fp = self.footprint_library.get(footprint_name)
        if fp is None:
            raise KeyError(f"footprint {footprint_name!r} not found")
        place = Placement(ref=ref, footprint=fp, x=x, y=y, rotation=rotation,
                          side=side, value=value)
        self.placements.append(place)
        return place

    def get_placement(self, ref) -> Optional[Placement]:
        for p in self.placements:
            if p.ref == ref:
                return p
        return None

    def add_trace(self, net, segments, layer="F.Cu", width=0.25):
        t = Trace(net=net, layer=layer, width=width)
        for (x1, y1, x2, y2) in segments:
            t.add_segment(x1, y1, x2, y2)
        self.traces.append(t)
        return t

    def add_via(self, x, y, net=None, drill=0.3, diameter=0.6):
        v = Via(x=x, y=y, drill=drill, diameter=diameter, net=net)
        self.vias.append(v)
        return v

    def add_zone(self, net="GND", layer="F.Cu", polygon=None):
        z = Zone(net=net, layer=layer,
                 polygon=polygon or list(self.outline))
        self.zones.append(z)
        return z

    # ---- ratsnest ----
    def ratsnest(self):
        """Compute the unrouted connections from the linked Netlist.

        Returns a list of (net_name, (x1,y1), (x2,y2)) for each pair.
        """
        if self.netlist is None:
            return []
        out = []
        for n in self.netlist.non_ground_nodes():
            positions = []
            for ref, pin_name in n.pins:
                p = self.get_placement(ref)
                if p:
                    try:
                        positions.append(p.pad_position(pin_name))
                    except KeyError:
                        pass
            for i in range(len(positions) - 1):
                out.append((n.name, positions[i], positions[i + 1]))
        return out

    # ---- summary ----
    def stats(self):
        return {
            "placements": len(self.placements),
            "traces": len(self.traces),
            "segments": sum(len(t.segments) for t in self.traces),
            "vias": len(self.vias),
            "zones": len(self.zones),
            "layers": len(self.layers),
            "copper_layers": len(self.layers.copper()),
        }
