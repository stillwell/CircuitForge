"""Voltage and current sources — DC, SIN, PULSE, PWL, EXP — plus controlled sources."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math
import numpy as np

from circuitforge.core.component import Component, Pin, ComponentType


@dataclass
class VoltageSource(Component):
    """Independent DC voltage source. The transient analysis can override
    the instantaneous value through update_source(t)."""
    component_type: ComponentType = ComponentType.SOURCE
    dc_value: float = 0.0
    ac_magnitude: float = 0.0
    ac_phase: float = 0.0

    def pin_definitions(self):
        return [Pin(name="+", number=1), Pin(name="-", number=2)]

    def num_extra_currents(self):
        return 1

    def _value_at(self, t):
        return self.dc_value if self.value is None else float(self.value)

    def stamp(self, ctx):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        if not hasattr(self, "_k") or self._k is None:
            self._k = ctx.alloc_extra()
        ctx.stamp_voltage_source(a, b, self._value_at(0.0), self._k)

    def stamp_ac(self, ctx, omega):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        if not hasattr(self, "_k") or self._k is None:
            self._k = ctx.alloc_extra()
        v = self.ac_magnitude * complex(math.cos(math.radians(self.ac_phase)),
                                        math.sin(math.radians(self.ac_phase)))
        ctx.stamp_voltage_source(a, b, v, self._k)

    def init_transient(self, dt, initial):
        self._k = None
        self._t = 0.0

    def stamp_transient(self, ctx, dt, prev):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        if self._k is None:
            self._k = ctx.alloc_extra()
        ctx.stamp_voltage_source(a, b, self._value_at(self._t), self._k)

    def update_source(self, ctx, t):
        self._t = t


@dataclass
class CurrentSource(Component):
    component_type: ComponentType = ComponentType.SOURCE
    dc_value: float = 0.0

    def pin_definitions(self):
        return [Pin(name="+", number=1), Pin(name="-", number=2)]

    def _value_at(self, t):
        return self.dc_value if self.value is None else float(self.value)

    def stamp(self, ctx):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        ctx.stamp_current(a, b, self._value_at(0.0))

    def stamp_ac(self, ctx, omega):
        self.stamp(ctx)

    def init_transient(self, dt, initial):
        self._t = 0.0

    def stamp_transient(self, ctx, dt, prev):
        a = ctx.node(self.pins[0].net)
        b = ctx.node(self.pins[1].net)
        ctx.stamp_current(a, b, self._value_at(self._t))

    def update_source(self, ctx, t):
        self._t = t


@dataclass
class SinSource(VoltageSource):
    """SIN(v_off v_amp freq td theta phase)"""
    v_offset: float = 0.0
    v_amp: float = 1.0
    freq: float = 1000.0
    td: float = 0.0
    theta: float = 0.0
    phase_deg: float = 0.0

    @classmethod
    def from_args(cls, ref, np_, nn, args):
        a = list(args) + [0.0] * 6
        s = cls(ref=ref, v_offset=a[0], v_amp=a[1], freq=a[2],
                td=a[3], theta=a[4], phase_deg=a[5])
        s.pins = [Pin(name="+", number=1, net=np_), Pin(name="-", number=2, net=nn)]
        return s

    def _value_at(self, t):
        if t < self.td:
            return self.v_offset + self.v_amp * math.sin(math.radians(self.phase_deg))
        damp = math.exp(-self.theta * (t - self.td)) if self.theta else 1.0
        return self.v_offset + self.v_amp * damp * math.sin(
            2 * math.pi * self.freq * (t - self.td) + math.radians(self.phase_deg))


@dataclass
class PulseSource(VoltageSource):
    """PULSE(v1 v2 td tr tf pw period)"""
    v1: float = 0.0
    v2: float = 1.0
    td: float = 0.0
    tr: float = 1e-9
    tf: float = 1e-9
    pw: float = 1e-3
    period: float = 2e-3

    @classmethod
    def from_args(cls, ref, np_, nn, args):
        a = list(args) + [0.0] * 7
        s = cls(ref=ref, v1=a[0], v2=a[1], td=a[2], tr=a[3], tf=a[4], pw=a[5], period=a[6])
        s.pins = [Pin(name="+", number=1, net=np_), Pin(name="-", number=2, net=nn)]
        return s

    def _value_at(self, t):
        if t < self.td:
            return self.v1
        local = (t - self.td) % self.period if self.period > 0 else t - self.td
        if local < self.tr:
            return self.v1 + (self.v2 - self.v1) * (local / self.tr)
        if local < self.tr + self.pw:
            return self.v2
        if local < self.tr + self.pw + self.tf:
            return self.v2 - (self.v2 - self.v1) * ((local - self.tr - self.pw) / self.tf)
        return self.v1


@dataclass
class PWLSource(VoltageSource):
    """PWL(t1 v1 t2 v2 ...) — piecewise-linear."""
    points: List[Tuple[float, float]] = field(default_factory=list)

    @classmethod
    def from_args(cls, ref, np_, nn, args):
        pts = [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
        s = cls(ref=ref, points=pts)
        s.pins = [Pin(name="+", number=1, net=np_), Pin(name="-", number=2, net=nn)]
        return s

    def _value_at(self, t):
        if not self.points:
            return 0.0
        if t <= self.points[0][0]:
            return self.points[0][1]
        for (t0, v0), (t1, v1) in zip(self.points, self.points[1:]):
            if t0 <= t <= t1:
                if t1 == t0:
                    return v1
                return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        return self.points[-1][1]


@dataclass
class ExpSource(VoltageSource):
    """EXP(v1 v2 td1 tau1 td2 tau2) — rising then falling exponential."""
    v1: float = 0.0
    v2: float = 1.0
    td1: float = 0.0
    tau1: float = 1e-3
    td2: float = 1e-3
    tau2: float = 1e-3

    def _value_at(self, t):
        if t < self.td1:
            return self.v1
        if t < self.td2:
            return self.v1 + (self.v2 - self.v1) * (1 - math.exp(-(t - self.td1) / self.tau1))
        rising = self.v1 + (self.v2 - self.v1) * (1 - math.exp(-(self.td2 - self.td1) / self.tau1))
        return self.v1 + (rising - self.v1) * math.exp(-(t - self.td2) / self.tau2)


# ---------- controlled sources ----------

@dataclass
class VCVS(Component):
    """Voltage-controlled voltage source: V(out+,out-) = gain * V(in+,in-)."""
    component_type: ComponentType = ComponentType.SOURCE
    gain: float = 1.0

    def __post_init__(self):
        if self.value is not None:
            self.gain = float(self.value)
        super().__post_init__()

    def pin_definitions(self):
        return [Pin(name="out+", number=1), Pin(name="out-", number=2),
                Pin(name="in+",  number=3), Pin(name="in-",  number=4)]

    def num_extra_currents(self):
        return 1

    def stamp(self, ctx):
        op = ctx.node(self.pins[0].net); on = ctx.node(self.pins[1].net)
        ip = ctx.node(self.pins[2].net); in_ = ctx.node(self.pins[3].net)
        k = ctx.alloc_extra()
        # KVL: V(op) - V(on) - gain*(V(ip) - V(in)) = 0
        if op is not None:
            ctx.G[op, k] += 1; ctx.G[k, op] += 1
        if on is not None:
            ctx.G[on, k] -= 1; ctx.G[k, on] -= 1
        if ip is not None:
            ctx.G[k, ip] -= self.gain
        if in_ is not None:
            ctx.G[k, in_] += self.gain

    stamp_ac = stamp
    stamp_transient = lambda self, ctx, dt, p: self.stamp(ctx)


@dataclass
class VCCS(Component):
    """Voltage-controlled current source: I(out+→out-) = gm * V(in+,in-)."""
    component_type: ComponentType = ComponentType.SOURCE
    gm: float = 1.0

    def __post_init__(self):
        if self.value is not None:
            self.gm = float(self.value)
        super().__post_init__()

    def pin_definitions(self):
        return [Pin(name="out+", number=1), Pin(name="out-", number=2),
                Pin(name="in+",  number=3), Pin(name="in-",  number=4)]

    def stamp(self, ctx):
        op = ctx.node(self.pins[0].net); on = ctx.node(self.pins[1].net)
        ip = ctx.node(self.pins[2].net); in_ = ctx.node(self.pins[3].net)
        ctx.stamp_vccs(op, on, ip, in_, self.gm)

    stamp_ac = stamp
    stamp_transient = lambda self, ctx, dt, p: self.stamp(ctx)


@dataclass
class CCVS(Component):
    """Current-controlled voltage source. value = transresistance r_m."""
    component_type: ComponentType = ComponentType.SOURCE
    r_m: float = 1.0
    sense_source: Optional[str] = None   # ref of V source that defines the sense current

    def pin_definitions(self):
        return [Pin(name="out+", number=1), Pin(name="out-", number=2)]

    def num_extra_currents(self):
        return 1


@dataclass
class CCCS(Component):
    """Current-controlled current source. value = beta."""
    component_type: ComponentType = ComponentType.SOURCE
    beta: float = 1.0
    sense_source: Optional[str] = None

    def pin_definitions(self):
        return [Pin(name="out+", number=1), Pin(name="out-", number=2)]
