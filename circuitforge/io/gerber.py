"""Gerber RS-274X export.

Generates one Gerber file per layer. The Gerber dialect emitted is the
modern extended format (RS-274X) with attributes — Eurocircuits/JLCPCB
and OSH Park accept this.
"""

import os
import time


_HEADER = """\
G04 CircuitForge Gerber RS-274X export*
%FSLAX46Y46*%
%MOMM*%
%LPD*%
G04 Aperture macros *
G75*
G01*
"""

_FOOTER = "M02*\n"


def _gerber_coord(x):
    """Convert mm float to 4.6 fixed-point string (Gerber format)."""
    return f"{int(round(x * 1_000_000))}"


def write_gerber(board, layer_name, path):
    """Write one Gerber file for a single layer."""
    apertures = {}                # (width, shape) -> code (D-code)
    next_code = 10
    body_lines = []

    def aperture_for(width, shape="round"):
        nonlocal next_code
        key = (round(width, 6), shape)
        if key in apertures:
            return apertures[key]
        code = next_code
        next_code += 1
        apertures[key] = code
        return code

    def emit_segment(x1, y1, x2, y2, width):
        d = aperture_for(width)
        body_lines.append(f"D{d}*")
        body_lines.append(f"X{_gerber_coord(x1)}Y{_gerber_coord(y1)}D02*")
        body_lines.append(f"X{_gerber_coord(x2)}Y{_gerber_coord(y2)}D01*")

    def emit_pad(x, y, w, h, shape):
        d = aperture_for(max(w, h), "rect" if shape == "rect" else "round")
        body_lines.append(f"D{d}*")
        body_lines.append(f"X{_gerber_coord(x)}Y{_gerber_coord(y)}D03*")

    # traces on this layer
    for t in board.traces:
        for s in t.segments:
            if s.layer == layer_name:
                emit_segment(s.x1, s.y1, s.x2, s.y2, s.width)

    # pads on this layer (only copper layers)
    if layer_name.endswith(".Cu"):
        for fpi in board.placements:
            for pad in fpi.footprint.pads:
                wants = (pad.layer == "*.Cu") or (pad.layer == layer_name) or \
                        (pad.layer == "F.Cu" and layer_name == "F.Cu") or \
                        (pad.layer == "B.Cu" and layer_name == "B.Cu")
                if wants:
                    emit_pad(fpi.x + pad.x, fpi.y + pad.y,
                             pad.width, pad.height, pad.shape.value)

    # vias appear on every copper layer
    if layer_name.endswith(".Cu"):
        for v in board.vias:
            emit_pad(v.x, v.y, v.diameter, v.diameter, "round")

    # board outline on Edge.Cuts
    if layer_name == "Edge.Cuts":
        outline_pts = board.outline
        for (x1, y1), (x2, y2) in zip(outline_pts, outline_pts[1:]):
            emit_segment(x1, y1, x2, y2, 0.05)

    # build aperture definitions block
    ap_defs = []
    for (width, shape), code in sorted(apertures.items(), key=lambda kv: kv[1]):
        if shape == "rect":
            ap_defs.append(f"%ADD{code}R,{width:.6f}X{width:.6f}*%")
        else:
            ap_defs.append(f"%ADD{code}C,{width:.6f}*%")

    text = (_HEADER
            + f"G04 Layer: {layer_name}*\n"
            + f"G04 Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n"
            + "\n".join(ap_defs) + "\n"
            + "\n".join(body_lines) + "\n"
            + _FOOTER)
    with open(path, "w") as f:
        f.write(text)
    return path


def write_gerber_set(board, output_dir):
    """Write all enabled layers to <output_dir> as a Gerber zip-ready set."""
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    extension_map = {
        "F.Cu": "GTL", "B.Cu": "GBL",
        "F.SilkS": "GTO", "B.SilkS": "GBO",
        "F.Mask": "GTS", "B.Mask": "GBS",
        "F.Paste": "GTP", "B.Paste": "GBP",
        "Edge.Cuts": "GKO",
    }
    for layer in board.layers:
        if not layer.enabled:
            continue
        ext = extension_map.get(layer.name, "GBR")
        safe = layer.name.replace(".", "_")
        path = os.path.join(output_dir, f"board-{safe}.{ext}")
        write_gerber(board, layer.name, path)
        paths.append(path)
    return paths
