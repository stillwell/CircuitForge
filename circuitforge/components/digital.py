"""Digital logic primitives — used for digital-domain (event-driven) simulation.

These are *not* full SPICE transistor-level models. They evaluate Boolean
expressions on their inputs (LOW < 1.5V, HIGH > 3.5V for TTL conventions),
update their outputs, and are stamped as voltage sources.
"""

from dataclasses import dataclass, field
from typing import List, Callable
import math

from circuitforge.core.component import Component, Pin, ComponentType


def _is_high(v, threshold=2.5):
    return v >= threshold


@dataclass
class _LogicGate(Component):
    component_type: ComponentType = ComponentType.DIGITAL
    vdd: float = 5.0
    vss: float = 0.0
    prop_delay: float = 10e-9
    n_inputs: int = 2

    def pin_definitions(self):
        pins = []
        for i in range(self.n_inputs):
            pins.append(Pin(name=f"IN{i+1}", number=i + 1, electrical_type="input"))
        pins.append(Pin(name="OUT", number=self.n_inputs + 1, electrical_type="output"))
        return pins

    def _logic(self, inputs):
        raise NotImplementedError

    def num_extra_currents(self):
        return 1

    def stamp(self, ctx):
        # Linear analysis: just clamp output to 0
        out = ctx.node(self.pins[-1].net)
        if not hasattr(self, "_k") or self._k is None:
            self._k = ctx.alloc_extra()
        ctx.stamp_voltage_source(out, None, 0.0, self._k)

    stamp_ac = stamp

    def init_transient(self, dt, initial):
        self._k = None
        self._last_out = self.vss
        self._t = 0.0

    def stamp_transient(self, ctx, dt, prev):
        out = ctx.node(self.pins[-1].net)
        if self._k is None:
            self._k = ctx.alloc_extra()
        # Read input voltages from prev solution. (Approximate — uses previous step.)
        inputs = []
        for p in self.pins[:-1]:
            idx = ctx.node(p.net)
            v = prev[idx].real if idx is not None else 0.0
            inputs.append(_is_high(v, (self.vdd + self.vss) / 2))
        result = self.vdd if self._logic(inputs) else self.vss
        # cheap RC-filtered transition (prop_delay)
        alpha = dt / max(self.prop_delay, dt)
        self._last_out = self._last_out + alpha * (result - self._last_out)
        ctx.stamp_voltage_source(out, None, self._last_out, self._k)


class AndGate(_LogicGate):
    def _logic(self, ins):
        return all(ins)


class OrGate(_LogicGate):
    def _logic(self, ins):
        return any(ins)


class NandGate(_LogicGate):
    def _logic(self, ins):
        return not all(ins)


class NorGate(_LogicGate):
    def _logic(self, ins):
        return not any(ins)


class XorGate(_LogicGate):
    def _logic(self, ins):
        return sum(ins) % 2 == 1


class XnorGate(_LogicGate):
    def _logic(self, ins):
        return sum(ins) % 2 == 0


@dataclass
class Inverter(_LogicGate):
    n_inputs: int = 1
    def _logic(self, ins):
        return not ins[0]


@dataclass
class Buffer(_LogicGate):
    n_inputs: int = 1
    def _logic(self, ins):
        return ins[0]


# ---------- flip-flops / latches ----------

@dataclass
class DFlipFlop(Component):
    component_type: ComponentType = ComponentType.DIGITAL
    vdd: float = 5.0
    vss: float = 0.0

    def pin_definitions(self):
        return [Pin(name="D",  number=1, electrical_type="input"),
                Pin(name="CLK", number=2, electrical_type="input"),
                Pin(name="Q",  number=3, electrical_type="output"),
                Pin(name="Q_", number=4, electrical_type="output")]

    def init_transient(self, dt, initial):
        self._q = 0
        self._last_clk = 0
        self._k_q = None; self._k_qn = None

    def num_extra_currents(self):
        return 2

    def stamp(self, ctx):
        if self._k_q is None:
            self._k_q = ctx.alloc_extra(); self._k_qn = ctx.alloc_extra()
        ctx.stamp_voltage_source(ctx.node(self.pins[2].net), None, self.vss, self._k_q)
        ctx.stamp_voltage_source(ctx.node(self.pins[3].net), None, self.vdd, self._k_qn)

    def stamp_transient(self, ctx, dt, prev):
        if self._k_q is None:
            self._k_q = ctx.alloc_extra(); self._k_qn = ctx.alloc_extra()
        di = ctx.node(self.pins[0].net); ci = ctx.node(self.pins[1].net)
        d_in = prev[di].real if di is not None else 0
        clk = prev[ci].real if ci is not None else 0
        threshold = (self.vdd + self.vss) / 2
        if clk > threshold and self._last_clk <= threshold:  # rising edge
            self._q = 1 if d_in > threshold else 0
        self._last_clk = clk
        vq = self.vdd if self._q else self.vss
        vqn = self.vss if self._q else self.vdd
        ctx.stamp_voltage_source(ctx.node(self.pins[2].net), None, vq, self._k_q)
        ctx.stamp_voltage_source(ctx.node(self.pins[3].net), None, vqn, self._k_qn)


@dataclass
class JKFlipFlop(Component):
    component_type: ComponentType = ComponentType.DIGITAL
    vdd: float = 5.0
    vss: float = 0.0

    def pin_definitions(self):
        return [Pin(name="J", number=1, electrical_type="input"),
                Pin(name="K", number=2, electrical_type="input"),
                Pin(name="CLK", number=3, electrical_type="input"),
                Pin(name="Q", number=4, electrical_type="output"),
                Pin(name="Q_", number=5, electrical_type="output")]


@dataclass
class SRLatch(Component):
    component_type: ComponentType = ComponentType.DIGITAL

    def pin_definitions(self):
        return [Pin(name="S", number=1), Pin(name="R", number=2),
                Pin(name="Q", number=3), Pin(name="Q_", number=4)]
