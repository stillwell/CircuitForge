"""Programmatic PCB construction example.

Builds a small board with a microcontroller, a regulator, and decoupling caps,
then exports KiCAD .kicad_pcb, Gerber, and Excellon drill files.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuitforge.core.netlist import Netlist
from circuitforge.core.component import Component, Pin
from circuitforge.components import Resistor, Capacitor, VoltageSource
from circuitforge.pcb import Board, GridRouter, DRC
from circuitforge.io import (write_kicad_pcb, write_gerber_set,
                             write_excellon, export_pcb_svg)


def main():
    nl = Netlist(name="example_board")
    # Power
    nl.add(VoltageSource(ref="V1", dc_value=5.0,
                         pins=[Pin(name="+", number=1, net="VCC"),
                               Pin(name="-", number=2, net="0")]))
    # Decoupling cap
    nl.add(Capacitor(ref="C1", value=100e-9,
                     pins=[Pin(name="1", number=1, net="VCC"),
                           Pin(name="2", number=2, net="0")]))
    # LED + resistor
    nl.add(Resistor(ref="R1", value=330,
                    pins=[Pin(name="1", number=1, net="VCC"),
                          Pin(name="2", number=2, net="LED")]))

    board = Board(width=40, height=30, copper_layers=2)
    board.netlist = nl
    board.title = "Example board"
    board.place("V1", "DIP-4", x=5, y=10)
    board.place("C1", "C_0805", x=15, y=10)
    board.place("R1", "R_0805", x=25, y=10)

    # ratsnest + autoroute
    rats = board.ratsnest()
    print(f"Ratsnest: {len(rats)} unrouted")
    router = GridRouter(board)
    routed = router.route_netlist(rats)
    print(f"Routed {len(routed)} nets")

    # DRC
    violations = DRC().run(board)
    print(f"DRC: {len(violations)} violations")

    # ground pour
    board.add_zone(net="0", layer="B.Cu",
                   polygon=[(0, 0), (40, 0), (40, 30), (0, 30)])

    # exports
    out_dir = os.path.dirname(__file__) + "/output"
    os.makedirs(out_dir, exist_ok=True)
    write_kicad_pcb(board, path=os.path.join(out_dir, "example.kicad_pcb"))
    write_gerber_set(board, os.path.join(out_dir, "gerbers"))
    write_excellon(board, os.path.join(out_dir, "example.drl"))
    export_pcb_svg(board, os.path.join(out_dir, "example.svg"))
    print(f"Exports in {out_dir}")


if __name__ == "__main__":
    main()
