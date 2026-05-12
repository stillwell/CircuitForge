"""SPICE deck import/export wrappers."""

from circuitforge.simulation.spice import parse_spice, write_spice


def read_spice_deck(path):
    """Parse a SPICE deck from disk. Returns (Netlist, directives)."""
    with open(path) as f:
        text = f.read()
    import os
    return parse_spice(text, base_dir=os.path.dirname(path))


def write_spice_deck(netlist, path, title=None):
    """Write a Netlist as a SPICE deck."""
    text = write_spice(netlist, title=title)
    with open(path, "w") as f:
        f.write(text)
    return path
