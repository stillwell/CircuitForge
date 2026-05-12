"""Smoke tests — verify the core modules import and basic flows work.

Run with: python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestUnits(unittest.TestCase):
    def test_parse_basic(self):
        from circuitforge.core.units import parse_value
        self.assertAlmostEqual(parse_value("4.7k"), 4700.0)
        self.assertAlmostEqual(parse_value("100n"), 1e-7)
        self.assertAlmostEqual(parse_value("1MEG"), 1e6)
        self.assertAlmostEqual(parse_value("2.5"), 2.5)
        self.assertAlmostEqual(parse_value("1u"), 1e-6)

    def test_format(self):
        from circuitforge.core.units import format_value
        self.assertEqual(format_value(0), "0")
        self.assertIn("k", format_value(4700))


class TestDivider(unittest.TestCase):
    """A 10k/10k divider from 5V should give 2.5V at the midpoint."""

    def test_op(self):
        from circuitforge.core.netlist import Netlist
        from circuitforge.core.component import Pin
        from circuitforge.components import Resistor, VoltageSource
        from circuitforge.simulation import dc_operating_point

        nl = Netlist()
        nl.add(VoltageSource(ref="V1", dc_value=5.0, pins=[
            Pin(name="+", number=1, net="vin"),
            Pin(name="-", number=2, net="0"),
        ]))
        nl.add(Resistor(ref="R1", value=10000.0, pins=[
            Pin(name="1", number=1, net="vin"),
            Pin(name="2", number=2, net="mid"),
        ]))
        nl.add(Resistor(ref="R2", value=10000.0, pins=[
            Pin(name="1", number=1, net="mid"),
            Pin(name="2", number=2, net="0"),
        ]))
        op = dc_operating_point(nl)
        self.assertAlmostEqual(op["vin"], 5.0, places=4)
        self.assertAlmostEqual(op["mid"], 2.5, places=4)


class TestSpiceImport(unittest.TestCase):
    """Round-trip a tiny SPICE deck."""

    def test_divider_deck(self):
        from circuitforge.simulation.spice import parse_spice
        from circuitforge.simulation import dc_operating_point
        text = """Divider
V1 vin 0 5
R1 vin mid 10k
R2 mid 0 10k
.op
.end
"""
        nl, _ = parse_spice(text)
        op = dc_operating_point(nl)
        self.assertAlmostEqual(op["mid"], 2.5, places=4)


class TestRCTransient(unittest.TestCase):
    """An RC charging from 0 to a step input."""

    def test_step_response(self):
        from circuitforge.core.netlist import Netlist
        from circuitforge.core.component import Pin
        from circuitforge.components import Resistor, Capacitor, VoltageSource
        from circuitforge.simulation import transient_analysis

        nl = Netlist()
        nl.add(VoltageSource(ref="V1", dc_value=1.0, pins=[
            Pin(name="+", number=1, net="in"),
            Pin(name="-", number=2, net="0"),
        ]))
        nl.add(Resistor(ref="R1", value=1000.0, pins=[
            Pin(name="1", number=1, net="in"),
            Pin(name="2", number=2, net="out"),
        ]))
        nl.add(Capacitor(ref="C1", value=1e-6, pins=[
            Pin(name="1", number=1, net="out"),
            Pin(name="2", number=2, net="0"),
        ]))
        t, wf = transient_analysis(nl, 0, 5e-3, 10e-6)
        # tau = RC = 1ms; at t=5tau, v_out should be > 0.99
        self.assertGreater(wf["out"][-1], 0.95)
        self.assertLess(wf["out"][0], 0.1)


class TestACAnalysis(unittest.TestCase):
    def test_rc_lowpass_cutoff(self):
        """At f_c the gain should be roughly -3 dB (≈ 0.707)."""
        import numpy as np
        from circuitforge.core.netlist import Netlist
        from circuitforge.core.component import Pin
        from circuitforge.components import Resistor, Capacitor, VoltageSource
        from circuitforge.simulation import ac_analysis

        R = 1000.0; C = 100e-9
        fc = 1 / (2 * np.pi * R * C)

        nl = Netlist()
        v = VoltageSource(ref="V1", dc_value=0.0, pins=[
            Pin(name="+", number=1, net="in"),
            Pin(name="-", number=2, net="0"),
        ])
        v.ac_magnitude = 1.0
        nl.add(v)
        nl.add(Resistor(ref="R1", value=R, pins=[
            Pin(name="1", number=1, net="in"),
            Pin(name="2", number=2, net="out"),
        ]))
        nl.add(Capacitor(ref="C1", value=C, pins=[
            Pin(name="1", number=1, net="out"),
            Pin(name="2", number=2, net="0"),
        ]))
        freqs, results = ac_analysis(nl, [fc])
        gain = abs(results["out"][0])
        self.assertAlmostEqual(gain, 0.707, places=2)


class TestBoardFlow(unittest.TestCase):
    def test_place_and_export_svg(self):
        import tempfile, os
        from circuitforge.pcb import Board
        from circuitforge.io import export_pcb_svg, write_excellon, write_gerber_set
        b = Board(width=20, height=20)
        b.place("R1", "R_0805", x=5, y=5)
        b.place("U1", "DIP-8",   x=12, y=10)
        with tempfile.TemporaryDirectory() as d:
            svg = os.path.join(d, "b.svg")
            drl = os.path.join(d, "b.drl")
            export_pcb_svg(b, svg)
            write_excellon(b, drl)
            paths = write_gerber_set(b, os.path.join(d, "gbr"))
            self.assertTrue(os.path.exists(svg))
            self.assertTrue(os.path.exists(drl))
            self.assertGreater(len(paths), 0)


class TestLibrary(unittest.TestCase):
    def test_library_loads(self):
        from circuitforge.components.library import ComponentLibrary
        lib = ComponentLibrary().load_default()
        self.assertGreater(len(lib), 50)
        self.assertIsNotNone(lib.get("NE555"))
        self.assertIsNotNone(lib.get("ATmega328P"))


if __name__ == "__main__":
    unittest.main()
