"""Passive components: resistor, capacitor, inductor, mutual inductor."""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from circuitforge.core.component import Component, Pin, ComponentType


@dataclass
class Resistor(Component):
    """Linear two-terminal resistor."""
    component_type: ComponentType = ComponentType.PASSIVE
    tolerance: float = 0.05      # ±5% default
    power_rating: float = 0.25   # watts

    def pin_definitions(self):
        return [Pin(name="1", number=1), Pin(name="2", number=2)]

    @property
    def resistance(self):
        return float(self.value) if self.value is not None else 1e9

    def stamp(self, ctx):
        g = 1.0 / self.resistance if self.resistance > 0 else 1e12
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        ctx.stamp_conductance(a, b, g)

    def stamp_ac(self, ctx, omega):
        self.stamp(ctx)

    def stamp_transient(self, ctx, dt, prev):
        self.stamp(ctx)


@dataclass
class Capacitor(Component):
    """Capacitor with backward-Euler companion model in transient.

        I_C = C * dV/dt  →  G_eq = C/dt, I_eq = C/dt * V_prev   (backward Euler)
                            G_eq = 2C/dt, I_eq = G_eq*V_prev + I_prev  (trapezoidal)
    """
    component_type: ComponentType = ComponentType.PASSIVE
    initial_voltage: float = 0.0
    esr: float = 0.0
    tolerance: float = 0.20

    def pin_definitions(self):
        return [Pin(name="1", number=1), Pin(name="2", number=2)]

    @property
    def capacitance(self):
        return float(self.value)

    # DC: capacitor is open circuit. Contribute nothing, but add a tiny
    # conductance to keep the matrix well-conditioned if it's the only path.
    def stamp(self, ctx):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        ctx.stamp_conductance(a, b, 1e-12)

    def stamp_ac(self, ctx, omega):
        # Y = j*omega*C
        y = 1j * omega * self.capacitance
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        ctx.stamp_conductance(a, b, y)

    def init_transient(self, dt, initial):
        self._v_prev = self.initial_voltage
        if initial:
            v1 = initial.get(self.pins[0].net, 0.0)
            v2 = initial.get(self.pins[1].net, 0.0)
            self._v_prev = v1 - v2

    def stamp_transient_method(self, ctx, dt, prev_sol, method):
        c = self.capacitance
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        v_prev = self._v_prev
        if method == "trap":
            g_eq = 2.0 * c / dt
            i_eq = g_eq * v_prev + getattr(self, "_i_prev", 0.0)
        else:  # backward Euler
            g_eq = c / dt
            i_eq = g_eq * v_prev
        ctx.stamp_conductance(a, b, g_eq)
        ctx.stamp_current(b, a, i_eq)   # flows from b to a (charges +)

    def stamp_transient(self, ctx, dt, prev_sol):
        self.stamp_transient_method(ctx, dt, prev_sol, "be")

    def advance_transient(self, sol, node_map, dt):
        a = node_map.get(self.pins[0].net)
        b = node_map.get(self.pins[1].net)
        va = sol[a].real if a is not None else 0.0
        vb = sol[b].real if b is not None else 0.0
        v_new = va - vb
        c = self.capacitance
        self._i_prev = c * (v_new - self._v_prev) / dt
        self._v_prev = v_new


@dataclass
class Inductor(Component):
    """Inductor — backward-Euler companion model in transient.

        V_L = L * dI/dt
        Companion: V = (L/dt) * (I - I_prev)
            → conductance form requires the auxiliary current.
    """
    component_type: ComponentType = ComponentType.PASSIVE
    initial_current: float = 0.0

    def pin_definitions(self):
        return [Pin(name="1", number=1), Pin(name="2", number=2)]

    @property
    def inductance(self):
        return float(self.value)

    def num_extra_currents(self):
        return 1

    # DC: short circuit. Use voltage-source-like stamp with V=0.
    def stamp(self, ctx):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        if not hasattr(self, "_k"):
            self._k = ctx.alloc_extra()
        ctx.stamp_voltage_source(a, b, 0.0, self._k)

    def stamp_ac(self, ctx, omega):
        # Z = j*omega*L → Y = 1/(j*omega*L)
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        z = 1j * omega * self.inductance
        if abs(z) < 1e-30:
            y = 1e12
        else:
            y = 1.0 / z
        ctx.stamp_conductance(a, b, y)

    def init_transient(self, dt, initial):
        self._i_prev = self.initial_current
        self._k = None

    def stamp_transient_method(self, ctx, dt, prev_sol, method):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        if self._k is None:
            self._k = ctx.alloc_extra()
        k = self._k
        L = self.inductance
        # V_a - V_b - (L/dt) * I = -(L/dt) * I_prev
        if a is not None:
            ctx.G[a, k] += 1.0
            ctx.G[k, a] += 1.0
        if b is not None:
            ctx.G[b, k] -= 1.0
            ctx.G[k, b] -= 1.0
        ctx.G[k, k] -= L / dt
        ctx.I[k] += -(L / dt) * self._i_prev

    def stamp_transient(self, ctx, dt, prev_sol):
        self.stamp_transient_method(ctx, dt, prev_sol, "be")

    def advance_transient(self, sol, node_map, dt):
        if self._k is not None:
            self._i_prev = sol[self._k].real


@dataclass
class MutualInductor(Component):
    """Coupled inductors. Wraps two Inductor refs and a coupling coefficient k."""
    component_type: ComponentType = ComponentType.PASSIVE
    inductor_a: Optional[str] = None
    inductor_b: Optional[str] = None
    k: float = 0.99

    def pin_definitions(self):
        return []

    def to_spice(self):
        return f"{self.ref} {self.inductor_a} {self.inductor_b} {self.k}"
