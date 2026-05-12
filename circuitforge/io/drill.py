"""Excellon NC drill file export."""

import time


def _excellon_coord(x):
    """Excellon coord in mm, integer microns (3.3 format)."""
    return f"{int(round(x * 1000))}"


def write_excellon(board, path, plated=True):
    """Write an Excellon (.drl) drill file.

    Aggregates all distinct drill diameters from pads + vias into tool slots.
    """
    holes = []   # list of (x, y, diameter, plated)
    for fpi in board.placements:
        for pad in fpi.footprint.pads:
            if pad.is_through_hole:
                holes.append((fpi.x + pad.x, fpi.y + pad.y,
                              pad.drill_diameter, True))
    for v in board.vias:
        holes.append((v.x, v.y, v.drill, True))

    # filter by plated/not
    holes = [h for h in holes if h[3] == plated]

    if not holes:
        with open(path, "w") as f:
            f.write("M48\nM30\n")
        return path

    # Build tool table
    tools = {}
    for (x, y, d, _) in holes:
        tools.setdefault(round(d, 4), len(tools) + 1)

    lines = []
    lines.append("M48")
    lines.append("; Excellon NC Drill file — CircuitForge")
    lines.append(f"; Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("FMAT,2")
    lines.append("METRIC,TZ")
    for diameter, tcode in sorted(tools.items(), key=lambda kv: kv[1]):
        lines.append(f"T{tcode:02d}C{diameter:.3f}")
    lines.append("%")
    lines.append("G90")
    lines.append("G05")
    lines.append("M71")  # metric
    # Drill operations grouped by tool
    for diameter, tcode in sorted(tools.items(), key=lambda kv: kv[1]):
        lines.append(f"T{tcode:02d}")
        for (x, y, d, _) in holes:
            if round(d, 4) == diameter:
                lines.append(f"X{_excellon_coord(x)}Y{_excellon_coord(y)}")
    lines.append("T0")
    lines.append("M30")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path
