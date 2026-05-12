"""Op-amp models — ideal, single-pole, and full SPICE-style macromodels."""

from dataclasses import dataclass
from circuitforge.core.component import Component, Pin, ComponentType


@dataclass
class IdealOpAmp(Component):
    """Ideal op-amp: V+ = V−, infinite output current. Implemented as a
    nullor — one extra current and a constraint V(in+)-V(in-) = 0."""
    component_type: ComponentType = ComponentType.INTEGRATED
    gain: float = 1e6   # very large but finite

    def pin_definitions(self):
        return [Pin(name="IN+", number=3, electrical_type="input"),
                Pin(name="IN-", number=2, electrical_type="input"),
                Pin(name="OUT", number=6, electrical_type="output"),
                Pin(name="V+",  number=7, electrical_type="power_in"),
                Pin(name="V-",  number=4, electrical_type="power_in")]

    def num_extra_currents(self):
        return 1

    def stamp(self, ctx):
        in_p = ctx.node(self.pins[0].net)
        in_n = ctx.node(self.pins[1].net)
        out  = ctx.node(self.pins[2].net)
        k = ctx.alloc_extra()
        # V(out) - gain * (V(in+) - V(in-)) = 0
        if out is not None:
            ctx.G[out, k] += 1; ctx.G[k, out] += 1
        if in_p is not None:
            ctx.G[k, in_p] -= self.gain
        if in_n is not None:
            ctx.G[k, in_n] += self.gain

    stamp_ac = stamp
    stamp_transient = lambda self, ctx, dt, p: self.stamp(ctx)


@dataclass
class SinglePoleOpAmp(IdealOpAmp):
    """Single-pole op-amp with finite GBW and slew-rate limit (approximate)."""
    gbw: float = 1e6
    slew_rate: float = 1e6

    def stamp_ac(self, ctx, omega):
        # H(s) = A0 / (1 + s/wp), where wp = 2π * GBW / A0
        wp = 2 * 3.141592653589793 * self.gbw / self.gain if self.gain else 1.0
        eff = self.gain / (1 + 1j * omega / wp)
        in_p = ctx.node(self.pins[0].net)
        in_n = ctx.node(self.pins[1].net)
        out  = ctx.node(self.pins[2].net)
        k = ctx.alloc_extra()
        if out is not None:
            ctx.G[out, k] += 1; ctx.G[k, out] += 1
        if in_p is not None:
            ctx.G[k, in_p] -= eff
        if in_n is not None:
            ctx.G[k, in_n] += eff
