"""Base classes for circuit components.

A Component is a generic schematic/simulation element with pins, parameters,
and a stamp() method that contributes to the MNA matrices. Concrete devices
live in circuitforge.components.*
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class ComponentType(Enum):
    PASSIVE = "passive"
    SOURCE = "source"
    SEMICONDUCTOR = "semiconductor"
    INTEGRATED = "integrated"
    DIGITAL = "digital"
    MECHANICAL = "mechanical"
    VIRTUAL = "virtual"


@dataclass
class Pin:
    """One terminal of a component."""
    name: str
    number: int = 0
    net: Optional[str] = None        # Connected net name (or None)
    x: float = 0.0                   # Schematic-local position
    y: float = 0.0
    electrical_type: str = "passive" # passive | input | output | power_in | power_out | bidi | nc

    def connect(self, net_name):
        self.net = net_name


@dataclass
class Component:
    """Base component class.

    Subclasses override pin_definitions() and stamp().
    """
    ref: str = ""                          # e.g. "R1", "U3"
    value: Any = None                      # e.g. 4700.0 (ohms) or "LM358"
    pins: List[Pin] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    component_type: ComponentType = ComponentType.PASSIVE

    # Schematic placement
    x: float = 0.0
    y: float = 0.0
    rotation: int = 0                      # degrees, multiples of 90
    mirror: bool = False

    # PCB
    footprint: Optional[str] = None

    # Cache for simulator
    _matrix_rows: List[int] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.pins:
            self.pins = self.pin_definitions()

    def pin_definitions(self):
        """Subclasses return their default pin list."""
        return []

    def get_pin(self, ident):
        for p in self.pins:
            if p.name == ident or p.number == ident:
                return p
        raise KeyError(f"pin {ident!r} not on {self.ref}")

    def connect(self, pin_ident, net_name):
        self.get_pin(pin_ident).net = net_name

    # ---- simulator interface (default: do nothing) ----
    def num_extra_currents(self):
        """Number of auxiliary current variables this device adds to MNA."""
        return 0

    def stamp(self, ctx):
        """Contribute conductance and source terms to the MNA system.

        ctx is a StampingContext (see simulation.mna) exposing:
            ctx.G[i,j] += g                   # conductance matrix
            ctx.B[i,k] = +/- 1                # incidence
            ctx.I[i]  += current              # current source vector
            ctx.E[k]  += voltage              # voltage source vector
            ctx.node(net_name) -> int         # node index (or None for ground)
        """
        pass

    def stamp_transient(self, ctx, dt, prev_solution):
        """Companion-model stamp for transient analysis (capacitors, inductors)."""
        self.stamp(ctx)

    def stamp_ac(self, ctx, omega):
        """AC small-signal stamp (override in reactive components)."""
        self.stamp(ctx)

    # ---- helpers ----
    def to_spice(self):
        """Return a SPICE netlist line for this component."""
        net_names = " ".join(p.net or "0" for p in self.pins)
        return f"{self.ref} {net_names} {self.value}"

    def __repr__(self):
        return f"<{type(self).__name__} {self.ref}={self.value}>"
