"""Semiconductor devices: diode, BJT, MOSFET, JFET.

These contribute via stamp_nonlinear() during Newton-Raphson. The linearization
is the standard small-signal companion model from Najm (Circuit Simulation, 2010).
"""

from dataclasses import dataclass, field
from typing import Optional
import math

from circuitforge.core.component import Component, Pin, ComponentType


VT_DEFAULT = 0.02585    # kT/q at ~300K


@dataclass
class Diode(Component):
    """Shockley diode model:  I = Is * (exp(V/(n*Vt)) - 1)"""
    component_type: ComponentType = ComponentType.SEMICONDUCTOR
    is_nonlinear: bool = True
    Is: float = 1e-14    # saturation current
    n: float = 1.0       # ideality factor
    Vt: float = VT_DEFAULT
    Rs: float = 0.0      # series resistance

    def pin_definitions(self):
        return [Pin(name="A", number=1), Pin(name="K", number=2)]

    def stamp(self, ctx):
        # DC linear stamp = very small conductance (open by default)
        a = ctx.node(self.pins[0].net); b = ctx.node(self.pins[1].net)
        ctx.stamp_conductance(a, b, 1e-12)

    def stamp_ac(self, ctx, omega):
        self.stamp(ctx)

    def stamp_transient(self, ctx, dt, prev):
        self.stamp(ctx)

    def stamp_nonlinear(self, ctx, x):
        a = ctx.node(self.pins[0].net); b = ctx.node(self.pins[1].net)
        va = x[a].real if a is not None else 0.0
        vb = x[b].real if b is not None else 0.0
        vd = va - vb
        # clamp to avoid overflow
        vd_eff = min(vd, 1.0)
        try:
            ex = math.exp(vd_eff / (self.n * self.Vt))
        except OverflowError:
            ex = 1e20
        Id = self.Is * (ex - 1.0)
        gd = self.Is * ex / (self.n * self.Vt)
        gd = max(gd, 1e-12)
        ieq = Id - gd * vd
        ctx.stamp_conductance(a, b, gd)
        ctx.stamp_current(b, a, ieq)


@dataclass
class BJT(Component):
    """Ebers-Moll BJT (PNP/NPN). Value is the model name; type set via params['type']."""
    component_type: ComponentType = ComponentType.SEMICONDUCTOR
    is_nonlinear: bool = True
    Is: float = 1e-15
    Bf: float = 100.0     # forward beta
    Br: float = 1.0       # reverse beta
    Vt: float = VT_DEFAULT
    type_: str = "NPN"

    def pin_definitions(self):
        return [Pin(name="C", number=1), Pin(name="B", number=2), Pin(name="E", number=3)]

    def stamp(self, ctx):
        for a, b in [(0, 1), (1, 2), (0, 2)]:
            ctx.stamp_conductance(ctx.node(self.pins[a].net),
                                  ctx.node(self.pins[b].net), 1e-12)

    def stamp_ac(self, ctx, omega):
        self.stamp(ctx)

    def stamp_transient(self, ctx, dt, prev):
        self.stamp(ctx)

    def stamp_nonlinear(self, ctx, x):
        sign = +1 if self.type_.upper() == "NPN" else -1
        c = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        e = ctx.node(self.pins[2].net)
        vbe = sign * ((x[b].real if b is not None else 0) - (x[e].real if e is not None else 0))
        vbc = sign * ((x[b].real if b is not None else 0) - (x[c].real if c is not None else 0))
        vbe_eff = min(vbe, 1.0); vbc_eff = min(vbc, 1.0)
        try:
            ex_be = math.exp(vbe_eff / self.Vt)
            ex_bc = math.exp(vbc_eff / self.Vt)
        except OverflowError:
            ex_be = ex_bc = 1e20
        # Ebers-Moll forward/reverse
        Ife = self.Is * (ex_be - 1)
        Ire = self.Is * (ex_bc - 1)
        Ic = Ife - Ire - Ire / self.Br
        Ib = Ife / self.Bf + Ire / self.Br
        Ie = -(Ic + Ib)

        gbe = self.Is * ex_be / self.Vt
        gbc = self.Is * ex_bc / self.Vt
        gbe = max(gbe, 1e-12); gbc = max(gbc, 1e-12)

        # crude small-signal linearization
        ctx.stamp_conductance(b, e, gbe / self.Bf)
        ctx.stamp_conductance(b, c, gbc / self.Br)
        ctx.stamp_vccs(c, e, b, e, gbe)  # forward transconductance
        # current correction
        ieq_c = sign * (Ic - gbe * vbe)
        ieq_b = sign * (Ib - gbe * vbe / self.Bf)
        ctx.stamp_current(c, e, ieq_c)
        ctx.stamp_current(b, e, ieq_b)


@dataclass
class MOSFET(Component):
    """Square-law MOSFET (Level 1)."""
    component_type: ComponentType = ComponentType.SEMICONDUCTOR
    is_nonlinear: bool = True
    Kp: float = 20e-6      # process transconductance
    W: float = 1e-6
    L: float = 1e-6
    Vth: float = 0.7
    lambda_: float = 0.0
    type_: str = "NMOS"    # NMOS / PMOS

    def pin_definitions(self):
        return [Pin(name="D", number=1), Pin(name="G", number=2),
                Pin(name="S", number=3), Pin(name="B", number=4)]

    def stamp(self, ctx):
        for a, b in [(0, 2), (1, 2), (0, 1)]:
            ctx.stamp_conductance(ctx.node(self.pins[a].net),
                                  ctx.node(self.pins[b].net), 1e-12)

    def stamp_ac(self, ctx, omega):
        self.stamp(ctx)

    def stamp_transient(self, ctx, dt, prev):
        self.stamp(ctx)

    def stamp_nonlinear(self, ctx, x):
        sign = +1 if self.type_.upper() == "NMOS" else -1
        d = ctx.node(self.pins[0].net)
        g = ctx.node(self.pins[1].net)
        s = ctx.node(self.pins[2].net)
        vd = x[d].real if d is not None else 0
        vg = x[g].real if g is not None else 0
        vs = x[s].real if s is not None else 0
        Vgs = sign * (vg - vs)
        Vds = sign * (vd - vs)
        beta = self.Kp * self.W / self.L
        Von = Vgs - self.Vth
        if Von <= 0:
            Id = 0.0
            gm = 1e-12; gds = 1e-12
        elif Vds < Von:
            Id = beta * (Von * Vds - 0.5 * Vds**2) * (1 + self.lambda_ * Vds)
            gm = beta * Vds
            gds = beta * (Von - Vds) + beta * self.lambda_ * (Von * Vds - 0.5 * Vds**2)
        else:
            Id = 0.5 * beta * Von**2 * (1 + self.lambda_ * Vds)
            gm = beta * Von * (1 + self.lambda_ * Vds)
            gds = 0.5 * beta * Von**2 * self.lambda_
        gm = max(gm, 1e-12); gds = max(gds, 1e-12)
        ctx.stamp_conductance(d, s, gds)
        ctx.stamp_vccs(d, s, g, s, gm)
        ieq = sign * (Id - gm * Vgs - gds * Vds)
        ctx.stamp_current(d, s, ieq)


@dataclass
class JFET(Component):
    """Simple JFET (saturation model). Pinout: D, G, S."""
    component_type: ComponentType = ComponentType.SEMICONDUCTOR
    is_nonlinear: bool = True
    Beta: float = 1e-3
    Vto: float = -2.0
    type_: str = "NJF"

    def pin_definitions(self):
        return [Pin(name="D", number=1), Pin(name="G", number=2), Pin(name="S", number=3)]

    def stamp(self, ctx):
        for a, b in [(0, 2), (1, 2), (0, 1)]:
            ctx.stamp_conductance(ctx.node(self.pins[a].net),
                                  ctx.node(self.pins[b].net), 1e-12)

    def stamp_nonlinear(self, ctx, x):
        # placeholder: very rough — replace with full model
        self.stamp(ctx)
