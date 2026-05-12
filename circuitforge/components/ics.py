"""Integrated-circuit packages.

These define pin maps and (for some) internal behavioral models. They are
useful for schematic capture and PCB layout even where the simulation model
is incomplete — the pin geometry is correct.
"""

from dataclasses import dataclass, field
from circuitforge.core.component import Component, Pin, ComponentType


def _dip(n):
    """Generate generic DIP-N package pins (no internal behavior)."""
    return [Pin(name=str(i), number=i) for i in range(1, n + 1)]


@dataclass
class IC555(Component):
    """NE555 timer (behavioral approximation)."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-8"

    def pin_definitions(self):
        return [
            Pin(name="GND", number=1, electrical_type="power_in"),
            Pin(name="TRIG", number=2, electrical_type="input"),
            Pin(name="OUT", number=3, electrical_type="output"),
            Pin(name="RESET", number=4, electrical_type="input"),
            Pin(name="CTRL", number=5, electrical_type="input"),
            Pin(name="THR", number=6, electrical_type="input"),
            Pin(name="DIS", number=7, electrical_type="bidi"),
            Pin(name="VCC", number=8, electrical_type="power_in"),
        ]


NE555 = IC555   # alias


@dataclass
class IC7400(Component):
    """Quad 2-input NAND."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-14"

    def pin_definitions(self):
        return _dip(14)


@dataclass
class IC7404(Component):
    """Hex inverter."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-14"

    def pin_definitions(self):
        return _dip(14)


@dataclass
class IC7408(Component):
    """Quad 2-input AND."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-14"

    def pin_definitions(self):
        return _dip(14)


@dataclass
class IC7432(Component):
    """Quad 2-input OR."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-14"

    def pin_definitions(self):
        return _dip(14)


@dataclass
class IC7474(Component):
    """Dual D flip-flop."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-14"

    def pin_definitions(self):
        return _dip(14)


@dataclass
class LM741(Component):
    """Single op-amp."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-8"

    def pin_definitions(self):
        return [
            Pin(name="OFFSET_N1", number=1),
            Pin(name="IN-", number=2, electrical_type="input"),
            Pin(name="IN+", number=3, electrical_type="input"),
            Pin(name="V-", number=4, electrical_type="power_in"),
            Pin(name="OFFSET_N2", number=5),
            Pin(name="OUT", number=6, electrical_type="output"),
            Pin(name="V+", number=7, electrical_type="power_in"),
            Pin(name="NC", number=8, electrical_type="nc"),
        ]


@dataclass
class LM358(Component):
    """Dual op-amp."""
    component_type: ComponentType = ComponentType.INTEGRATED
    package: str = "DIP-8"

    def pin_definitions(self):
        return [
            Pin(name="OUT_A", number=1, electrical_type="output"),
            Pin(name="IN_A-", number=2, electrical_type="input"),
            Pin(name="IN_A+", number=3, electrical_type="input"),
            Pin(name="VCC", number=4, electrical_type="power_in"),
            Pin(name="IN_B+", number=5, electrical_type="input"),
            Pin(name="IN_B-", number=6, electrical_type="input"),
            Pin(name="OUT_B", number=7, electrical_type="output"),
            Pin(name="VEE", number=8, electrical_type="power_in"),
        ]
