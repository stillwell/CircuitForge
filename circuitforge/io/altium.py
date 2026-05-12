"""Altium Designer importer (partial, ASCII formats only).

Modern Altium files (.SchDoc, .PcbDoc) are OLE compound documents that
require external tooling to parse fully. We support the older ASCII-export
formats (.SchLib ASCII, .PcbLib ASCII) and Altium's netlist (.NET).
"""


def read_altium_sch(path):
    """Read an Altium ASCII schematic export. Returns a Netlist (partial)."""
    from circuitforge.core.netlist import Netlist
    from circuitforge.core.component import Component, Pin

    nl = Netlist(name=path)
    current_comp = None
    components_by_designator = {}

    with open(path, encoding="latin-1") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                # section header — finalize prior component
                if current_comp:
                    components_by_designator[current_comp.ref] = current_comp
                current_comp = None
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key == "designator":
                current_comp = Component(ref=value)
            elif current_comp and key == "comment":
                current_comp.value = value
            elif current_comp and key == "footprint":
                current_comp.footprint = value

    for c in components_by_designator.values():
        nl.add(c)
    return nl
