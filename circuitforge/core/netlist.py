"""Netlist data structure — the canonical representation of a circuit.

A Netlist owns a set of nodes (electrical nets) and components. Components
reference nets by name. Node "0" / "GND" is always ground.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional


GROUND_ALIASES = {"0", "gnd", "GND", "ground", "Ground", "VSS", "vss"}


@dataclass
class Node:
    """An electrical net."""
    name: str
    pins: List = field(default_factory=list)   # list of (component_ref, pin_ident)

    @property
    def is_ground(self):
        return self.name in GROUND_ALIASES


class Netlist:
    """The full circuit: components + nets."""

    def __init__(self, name="untitled"):
        self.name = name
        self.components = []          # type: List[Component]
        self._nodes = {}              # type: Dict[str, Node]
        self.directives = []          # SPICE-style .options, .tran, etc.

    # ---- node management ----
    def node(self, name):
        if name in GROUND_ALIASES:
            name = "0"
        if name not in self._nodes:
            self._nodes[name] = Node(name)
        return self._nodes[name]

    def nodes(self):
        return list(self._nodes.values())

    def non_ground_nodes(self):
        return [n for n in self._nodes.values() if not n.is_ground]

    def node_index_map(self):
        """Return {node_name: matrix_row_index} with ground excluded."""
        mapping = {}
        idx = 0
        for n in self._nodes.values():
            if n.is_ground:
                continue
            mapping[n.name] = idx
            idx += 1
        return mapping

    # ---- component management ----
    def add(self, component):
        self.components.append(component)
        for p in component.pins:
            if p.net is not None:
                node = self.node(p.net)
                node.pins.append((component.ref, p.name))
        return component

    def remove(self, ref):
        comp = self.get(ref)
        if comp is None:
            return
        self.components.remove(comp)
        for n in self._nodes.values():
            n.pins = [(r, p) for r, p in n.pins if r != ref]

    def get(self, ref):
        for c in self.components:
            if c.ref == ref:
                return c
        return None

    def __iter__(self):
        return iter(self.components)

    def __len__(self):
        return len(self.components)

    # ---- analysis prep ----
    def voltage_sources(self):
        from circuitforge.components.sources import VoltageSource
        return [c for c in self.components if isinstance(c, VoltageSource)]

    def count_extra_currents(self):
        return sum(c.num_extra_currents() for c in self.components)

    # ---- ERC (electrical rules check) ----
    def erc(self):
        """Run basic electrical rules checks. Returns list of (severity, message)."""
        issues = []
        # Check floating pins (nodes with only one pin)
        for n in self._nodes.values():
            if n.is_ground:
                continue
            if len(n.pins) < 2:
                issues.append(("warning", f"net '{n.name}' has only {len(n.pins)} connection(s)"))
        # Check duplicate refs
        seen = set()
        for c in self.components:
            if c.ref in seen:
                issues.append(("error", f"duplicate reference designator: {c.ref}"))
            seen.add(c.ref)
        # Check unconnected pins
        for c in self.components:
            for p in c.pins:
                if p.net is None and p.electrical_type != "nc":
                    issues.append(("warning", f"{c.ref}.{p.name} is unconnected"))
        return issues

    def summary(self):
        return (f"Netlist {self.name!r}: {len(self.components)} components, "
                f"{len(self._nodes)} nets")

    def __repr__(self):
        return f"<Netlist {self.name!r} components={len(self.components)} nodes={len(self._nodes)}>"
