"""Eagle (.sch / .brd) XML importer — partial.

Eagle files are XML. We use ElementTree from the stdlib to avoid extra deps.
This importer extracts parts, nets, and (for .brd) wires/pads at a basic level.
"""

import xml.etree.ElementTree as ET


def read_eagle_sch(path):
    """Read an Eagle .sch file. Returns a Netlist."""
    from circuitforge.core.netlist import Netlist
    from circuitforge.core.component import Component, Pin

    tree = ET.parse(path)
    root = tree.getroot()
    nl = Netlist(name=path)
    parts = {}
    for part in root.iter("part"):
        name = part.get("name")
        value = part.get("value", "")
        comp = Component(ref=name, value=value)
        parts[name] = comp
    # nets / signals
    for net in root.iter("net"):
        net_name = net.get("name")
        for pinref in net.iter("pinref"):
            part_name = pinref.get("part")
            pin_name = pinref.get("pin")
            if part_name in parts:
                comp = parts[part_name]
                # add pin if not present
                try:
                    comp.get_pin(pin_name)
                except KeyError:
                    comp.pins.append(Pin(name=pin_name, number=len(comp.pins) + 1))
                comp.connect(pin_name, net_name)
    for c in parts.values():
        nl.add(c)
    return nl


def read_eagle_brd(path):
    """Read an Eagle .brd file (board). Returns a Board (partial)."""
    from circuitforge.pcb.editor import Board
    from circuitforge.pcb.footprint import Footprint
    from circuitforge.pcb.pad import Pad, PadShape

    tree = ET.parse(path)
    root = tree.getroot()
    board = Board(width=100, height=80)
    libraries = {}
    # parse package definitions
    for lib in root.iter("library"):
        lib_name = lib.get("name", "")
        for pkg in lib.iter("package"):
            pkg_name = pkg.get("name")
            fp = Footprint(name=pkg_name)
            for pad in pkg.iter("pad"):
                fp.pads.append(Pad(
                    name=pad.get("name"),
                    x=float(pad.get("x", 0)),
                    y=float(pad.get("y", 0)),
                    width=float(pad.get("diameter", 1.5)),
                    height=float(pad.get("diameter", 1.5)),
                    shape=PadShape.CIRCLE,
                    drill_diameter=float(pad.get("drill", 0.8)),
                    layer="*.Cu",
                ))
            for smd in pkg.iter("smd"):
                fp.pads.append(Pad(
                    name=smd.get("name"),
                    x=float(smd.get("x", 0)),
                    y=float(smd.get("y", 0)),
                    width=float(smd.get("dx", 1)),
                    height=float(smd.get("dy", 1)),
                    shape=PadShape.RECT,
                    drill_diameter=0.0,
                    layer="F.Cu",
                ))
            libraries[(lib_name, pkg_name)] = fp
            board.footprint_library.register(fp)
    # elements
    for elem in root.iter("element"):
        name = elem.get("name")
        lib_name = elem.get("library")
        pkg_name = elem.get("package")
        x = float(elem.get("x", 0)); y = float(elem.get("y", 0))
        rot_str = elem.get("rot", "R0")
        rot = float(rot_str[1:]) if rot_str.startswith("R") else 0.0
        fp = libraries.get((lib_name, pkg_name))
        if fp is not None:
            board.place(name, fp.name, x, y, rot)
    # signals → traces
    for signal in root.iter("signal"):
        net = signal.get("name")
        for wire in signal.iter("wire"):
            x1 = float(wire.get("x1")); y1 = float(wire.get("y1"))
            x2 = float(wire.get("x2")); y2 = float(wire.get("y2"))
            w = float(wire.get("width", 0.25))
            layer = wire.get("layer", "1")
            layer_name = {"1": "F.Cu", "16": "B.Cu"}.get(layer, "F.Cu")
            board.add_trace(net, [(x1, y1, x2, y2)], layer=layer_name, width=w)
    return board
