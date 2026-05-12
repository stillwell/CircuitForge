"""KiCAD S-expression file format I/O.

We target KiCAD v6+ formats:
    .kicad_sch — schematic
    .kicad_pcb — board
    .kicad_sym — symbol library
    .kicad_mod — footprint (single)
    .kicad_pro — project

This is a partial implementation — sufficient to round-trip the major
entities (components, wires, footprints, pads, traces, vias, zones).
Layout-level proprietary features (3D models, custom rules) are passed
through as opaque sexpr lists where possible.
"""

import uuid
import time

from .sexpr import parse, dump, dump_pretty


# ---------------- schematic -----------------------------------------------

def write_kicad_sch(canvas, netlist=None, path=None, title=None):
    """Serialize a SchematicCanvas to KiCAD v6 .kicad_sch format."""
    root = ["kicad_sch", ["version", 20211123], ["generator", "circuitforge"]]
    root.append(["uuid", str(uuid.uuid4())])
    root.append(["paper", "A4"])

    # title block
    tb = ["title_block",
          ["title", title or canvas.placements and "Schematic" or "Untitled"],
          ["date", time.strftime("%Y-%m-%d")],
          ["company", "CircuitForge"]]
    root.append(tb)

    # symbols
    for p in canvas.placements:
        sym = ["symbol",
               ["lib_id", f"local:{p.type_name}"],
               ["at", float(p.x), float(p.y), int(p.rotation)],
               ["uuid", str(uuid.uuid4())],
               ["property", "Reference", p.component_ref,
                ["at", float(p.x), float(p.y - 5), 0]],
               ]
        root.append(sym)

    # wires
    for w in canvas.wires:
        for (x1, y1), (x2, y2) in zip(w.points, w.points[1:]):
            root.append(["wire",
                         ["pts", ["xy", float(x1), float(y1)], ["xy", float(x2), float(y2)]],
                         ["stroke", ["width", 0.0], ["type", "default"]],
                         ["uuid", str(uuid.uuid4())]])

    # net labels
    for lbl in canvas.labels:
        root.append(["label", lbl.name,
                     ["at", float(lbl.x), float(lbl.y), int(lbl.rotation)],
                     ["uuid", str(uuid.uuid4())]])

    text = dump_pretty(root)
    if path:
        with open(path, "w") as f:
            f.write(text + "\n")
    return text


def read_kicad_sch(path):
    """Parse a .kicad_sch file. Returns a SchematicCanvas."""
    from circuitforge.schematic.canvas import SchematicCanvas, PlacedSymbol, NetLabel
    from circuitforge.schematic.wire import Wire

    with open(path) as f:
        root = parse(f.read())
    canvas = SchematicCanvas()
    for item in root[1:]:
        if not isinstance(item, list) or not item:
            continue
        tag = item[0]
        if tag == "symbol":
            lib_id = _find(item, "lib_id", "default:Unknown")
            at = _find(item, "at", [0, 0, 0])
            ref = _find_property(item, "Reference", "U?")
            tname = lib_id.split(":")[-1] if isinstance(lib_id, str) else "Unknown"
            canvas.placements.append(PlacedSymbol(
                component_ref=ref, type_name=tname,
                x=float(at[0]) if len(at) > 0 else 0,
                y=float(at[1]) if len(at) > 1 else 0,
                rotation=int(at[2]) if len(at) > 2 else 0,
            ))
        elif tag == "wire":
            pts = next((p for p in item if isinstance(p, list) and p[0] == "pts"), None)
            if pts:
                points = []
                for sub in pts[1:]:
                    if isinstance(sub, list) and sub[0] == "xy" and len(sub) >= 3:
                        points.append((float(sub[1]), float(sub[2])))
                if points:
                    canvas.wires.append(Wire(points=points))
        elif tag == "label" and len(item) >= 2:
            name = item[1]
            at = _find(item, "at", [0, 0, 0])
            canvas.labels.append(NetLabel(
                name=str(name),
                x=float(at[0]) if len(at) > 0 else 0,
                y=float(at[1]) if len(at) > 1 else 0,
                rotation=int(at[2]) if len(at) > 2 else 0))
    return canvas


# ---------------- PCB -----------------------------------------------------

def write_kicad_pcb(board, path=None, title=None):
    """Serialize a Board to .kicad_pcb."""
    root = ["kicad_pcb", ["version", 20221018], ["generator", "circuitforge"]]
    root.append(["general", ["thickness", 1.6]])
    root.append(["paper", "A4"])

    # layers
    layers = ["layers"]
    for i, l in enumerate(board.layers):
        layers.append([l.number, l.name, _kicad_layer_type(l.type_), l.name])
    root.append(layers)

    # setup
    root.append(["setup", ["pad_to_mask_clearance", 0.0]])

    # net listing
    nets = ["net", 0, ""]
    root.append(nets)
    if board.netlist is not None:
        for i, n in enumerate(board.netlist.non_ground_nodes(), start=1):
            root.append(["net", i, n.name])

    # footprints
    for fpi in board.placements:
        fp = ["footprint", fpi.footprint.name,
              ["layer", "F.Cu" if fpi.side == "top" else "B.Cu"],
              ["at", float(fpi.x), float(fpi.y), float(fpi.rotation)],
              ["tedit", hex(int(time.time()))],
              ["tstamp", str(uuid.uuid4())]]
        for pad in fpi.footprint.pads:
            kind = "thru_hole" if pad.is_through_hole else "smd"
            shape = pad.shape.value
            fp.append(["pad", pad.name, kind, shape,
                       ["at", float(pad.x), float(pad.y)],
                       ["size", float(pad.width), float(pad.height)],
                       ["layers", pad.layer]] +
                      ([["drill", float(pad.drill_diameter)]] if pad.is_through_hole else []))
        root.append(fp)

    # traces
    for t in board.traces:
        for s in t.segments:
            root.append(["segment",
                         ["start", float(s.x1), float(s.y1)],
                         ["end",   float(s.x2), float(s.y2)],
                         ["width", float(s.width)],
                         ["layer", s.layer],
                         ["net",   _net_id(board, s.net or t.net)]])

    # vias
    for v in board.vias:
        root.append(["via",
                     ["at", float(v.x), float(v.y)],
                     ["size", float(v.diameter)],
                     ["drill", float(v.drill)],
                     ["layers", v.layer_from, v.layer_to],
                     ["net", _net_id(board, v.net)]])

    # zones
    for z in board.zones:
        zone = ["zone",
                ["net", _net_id(board, z.net)],
                ["net_name", z.net],
                ["layer", z.layer],
                ["clearance", float(z.clearance)],
                ["min_thickness", float(z.min_thickness)]]
        polygon = ["polygon", ["pts"]]
        for (x, y) in z.polygon:
            polygon[1].append(["xy", float(x), float(y)])
        zone.append(polygon)
        root.append(zone)

    text = dump_pretty(root)
    if path:
        with open(path, "w") as f:
            f.write(text + "\n")
    return text


def read_kicad_pcb(path):
    """Parse a .kicad_pcb file. Returns a Board (partial — best-effort)."""
    from circuitforge.pcb.editor import Board
    from circuitforge.pcb.footprint import Footprint
    from circuitforge.pcb.pad import Pad, PadShape

    with open(path) as f:
        root = parse(f.read())
    board = Board(copper_layers=2)
    fp_lookup = {}
    for item in root[1:]:
        if not isinstance(item, list) or not item:
            continue
        if item[0] == "footprint":
            name = item[1] if len(item) > 1 else "unknown"
            fp = Footprint(name=name)
            at = _find(item, "at", [0, 0, 0])
            x = float(at[0]) if len(at) > 0 else 0
            y = float(at[1]) if len(at) > 1 else 0
            rot = float(at[2]) if len(at) > 2 else 0
            ref = _find_property(item, "Reference", "U?")
            for sub in item[2:]:
                if isinstance(sub, list) and sub[0] == "pad" and len(sub) >= 4:
                    pname = str(sub[1])
                    kind = sub[2]; shape_str = sub[3]
                    pat = _find(sub, "at", [0, 0])
                    psize = _find(sub, "size", [1, 1])
                    drill = _find(sub, "drill", 0.0)
                    try:
                        shape = PadShape(shape_str)
                    except ValueError:
                        shape = PadShape.CIRCLE
                    fp.pads.append(Pad(
                        name=pname,
                        x=float(pat[0]) if len(pat) > 0 else 0,
                        y=float(pat[1]) if len(pat) > 1 else 0,
                        width=float(psize[0]),
                        height=float(psize[1]),
                        shape=shape,
                        drill_diameter=float(drill) if isinstance(drill, (int, float)) else 0.0,
                    ))
            board.footprint_library.register(fp)
            board.place(ref, fp.name, x, y, rot)
        elif item[0] == "segment":
            start = _find(item, "start", [0, 0])
            end = _find(item, "end", [0, 0])
            width = _find(item, "width", 0.25)
            layer = _find(item, "layer", "F.Cu")
            board.add_trace("", [(start[0], start[1], end[0], end[1])],
                            layer=str(layer), width=float(width))
        elif item[0] == "via":
            at = _find(item, "at", [0, 0])
            drill = _find(item, "drill", 0.3)
            size = _find(item, "size", 0.6)
            board.add_via(float(at[0]), float(at[1]), drill=float(drill),
                          diameter=float(size))
    return board


# ---------------- symbol & footprint libraries ----------------------------

def write_kicad_sym(symbol, name=None):
    """Serialize a Symbol to a single .kicad_sym entry."""
    name = name or symbol.name
    root = ["kicad_symbol_lib", ["version", 20211014], ["generator", "circuitforge"],
            ["symbol", name]]
    sym = root[3]
    for prim in symbol.primitives:
        if prim.kind == "line" and len(prim.points) >= 2:
            (x1, y1), (x2, y2) = prim.points[:2]
            sym.append(["polyline",
                        ["pts", ["xy", x1, y1], ["xy", x2, y2]],
                        ["stroke", ["width", 0.254], ["type", "default"]]])
        elif prim.kind == "rect" and len(prim.points) >= 2:
            (x1, y1), (x2, y2) = prim.points[:2]
            sym.append(["rectangle", ["start", x1, y1], ["end", x2, y2]])
        elif prim.kind == "circle" and prim.points:
            cx, cy = prim.points[0]
            sym.append(["circle", ["center", cx, cy], ["radius", prim.radius]])
    return dump_pretty(root)


def write_kicad_mod(footprint, path=None):
    """Serialize a Footprint to .kicad_mod."""
    root = ["module", footprint.name,
            ["layer", "F.Cu"],
            ["tedit", hex(int(time.time()))]]
    for pad in footprint.pads:
        kind = "thru_hole" if pad.is_through_hole else "smd"
        root.append(["pad", pad.name, kind, pad.shape.value,
                     ["at", float(pad.x), float(pad.y)],
                     ["size", float(pad.width), float(pad.height)],
                     ["layers", pad.layer]] +
                    ([["drill", float(pad.drill_diameter)]] if pad.is_through_hole else []))
    text = dump_pretty(root)
    if path:
        with open(path, "w") as f:
            f.write(text + "\n")
    return text


# ---------------- helpers -------------------------------------------------

def _find(node, key, default):
    for child in node:
        if isinstance(child, list) and len(child) >= 2 and child[0] == key:
            return child[1:] if len(child) > 2 else child[1]
    return default


def _find_property(node, prop_name, default):
    for child in node:
        if (isinstance(child, list) and len(child) >= 3
                and child[0] == "property" and child[1] == prop_name):
            return child[2]
    return default


def _net_id(board, net_name):
    if board.netlist is None or net_name is None:
        return 0
    for i, n in enumerate(board.netlist.non_ground_nodes(), start=1):
        if n.name == net_name:
            return i
    return 0


def _kicad_layer_type(type_):
    return {
        "copper": "signal", "silk": "user", "mask": "user",
        "paste": "user", "drawing": "user", "edge": "user",
        "mechanical": "user"
    }.get(type_, "user")
