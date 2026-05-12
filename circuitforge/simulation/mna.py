"""Modified Nodal Analysis (MNA) matrix builder.

We solve

    [ G  B ] [v]   [ I ]
    [ C  D ] [j] = [ E ]

where
    G — node-to-node conductance (N×N)
    B — incidence of voltage sources / extra-current devices (N×M)
    C — typically B.T
    D — extra constraints (M×M, often zero)
    v — unknown node voltages (N)
    j — unknown currents through voltage-defined devices (M)
    I — current source vector (N)
    E — voltage source vector (M)

N = number of non-ground nodes.  M = number of extra-current variables.

This is the textbook formulation (Ho/Ruehli/Brennan 1975) and matches what
SPICE-derived simulators do under the hood.
"""

import numpy as np


class StampingContext:
    """Passed to each component's stamp() method.

    Provides indexed access to the MNA matrix blocks and helpers for
    looking up node indices.
    """

    __slots__ = ("G", "B", "C", "D", "I", "E", "_node_map", "_next_extra",
                 "n_nodes", "n_extra", "complex_mode")

    def __init__(self, n_nodes, n_extra, node_map, complex_mode=False):
        dtype = complex if complex_mode else float
        self.n_nodes = n_nodes
        self.n_extra = n_extra
        size = n_nodes + n_extra
        self.G = np.zeros((size, size), dtype=dtype)  # combined system
        self.B = self.G                                # alias for clarity
        self.C = self.G
        self.D = self.G
        self.I = np.zeros(size, dtype=dtype)
        self.E = self.I
        self._node_map = node_map
        self._next_extra = n_nodes
        self.complex_mode = complex_mode

    def node(self, name):
        """Return matrix row index for a net name, or None for ground."""
        if name is None:
            return None
        if name in ("0", "gnd", "GND", "ground", "Ground", "VSS", "vss"):
            return None
        return self._node_map.get(name)

    def alloc_extra(self):
        """Reserve one row/column for an auxiliary current variable."""
        k = self._next_extra
        self._next_extra += 1
        return k

    def stamp_conductance(self, a, b, g):
        """Stamp a conductance g between nodes a and b (indices or None)."""
        if a is not None:
            self.G[a, a] += g
        if b is not None:
            self.G[b, b] += g
        if a is not None and b is not None:
            self.G[a, b] -= g
            self.G[b, a] -= g

    def stamp_current(self, src, dst, i):
        """Stamp a current source of value i flowing from src to dst."""
        if src is not None:
            self.I[src] -= i
        if dst is not None:
            self.I[dst] += i

    def stamp_voltage_source(self, a, b, v, k):
        """Stamp a voltage source v between a and b using extra-current row k.

        The branch current j flows from a (positive terminal) to b.
        """
        if a is not None:
            self.G[a, k] += 1.0
            self.G[k, a] += 1.0
        if b is not None:
            self.G[b, k] -= 1.0
            self.G[k, b] -= 1.0
        self.I[k] += v

    def stamp_vccs(self, a, b, c, d, gm):
        """Voltage-Controlled Current Source: current from a→b proportional to V(c)-V(d).

            I(a,b) = gm * (V(c) - V(d))
        """
        if a is not None and c is not None:
            self.G[a, c] += gm
        if a is not None and d is not None:
            self.G[a, d] -= gm
        if b is not None and c is not None:
            self.G[b, c] -= gm
        if b is not None and d is not None:
            self.G[b, d] += gm


class MNABuilder:
    """Assembles an MNA system from a Netlist."""

    def __init__(self, netlist):
        self.netlist = netlist
        self.node_map = netlist.node_index_map()
        self.n_nodes = len(self.node_map)
        self.n_extra = netlist.count_extra_currents()
        # reverse map for results
        self.index_to_node = {v: k for k, v in self.node_map.items()}

    def build(self, complex_mode=False, callback=None):
        """Build (and return) the MNA system. `callback(ctx, component)` lets
        callers override stamping (used for transient & AC)."""
        ctx = StampingContext(self.n_nodes, self.n_extra, self.node_map, complex_mode)
        for comp in self.netlist.components:
            if callback is not None:
                callback(ctx, comp)
            else:
                comp.stamp(ctx)
        return ctx

    def solve(self, ctx):
        """Solve the assembled system. Returns the solution vector."""
        try:
            return np.linalg.solve(ctx.G, ctx.I)
        except np.linalg.LinAlgError:
            # Singular: fall back to least-squares (gives some result for diagnosis)
            sol, *_ = np.linalg.lstsq(ctx.G, ctx.I, rcond=None)
            return sol

    def unpack(self, solution):
        """Map a raw solution vector back to {node_name: value}."""
        result = {"0": 0.0}
        for i, name in self.index_to_node.items():
            result[name] = solution[i]
        return result
