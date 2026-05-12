"""SVG export for schematics and boards."""


def export_schematic_svg(canvas, path):
    text = canvas.to_svg()
    with open(path, "w") as f:
        f.write(text)
    return path


def export_pcb_svg(board, path):
    """Render a board as a layered SVG (top + bottom copper + silk)."""
    out = ['<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="0 0 {board.width} {board.height}" '
           f'width="{board.width * 5}" height="{board.height * 5}">']
    out.append('<rect x="0" y="0" width="100%" height="100%" fill="#003300"/>')

    # board outline
    pts = " ".join(f"{x},{y}" for x, y in board.outline)
    out.append(f'<polyline points="{pts}" fill="none" stroke="yellow" stroke-width="0.1"/>')

    # zones (background)
    for z in board.zones:
        if z.polygon:
            pts = " ".join(f"{x},{y}" for x, y in z.polygon)
            color = "#660000" if z.layer == "F.Cu" else "#000066"
            out.append(f'<polygon points="{pts}" fill="{color}" opacity="0.3"/>')

    # traces
    for t in board.traces:
        for s in t.segments:
            color = "#cc3333" if s.layer == "F.Cu" else "#3333cc"
            out.append(
                f'<line x1="{s.x1}" y1="{s.y1}" x2="{s.x2}" y2="{s.y2}" '
                f'stroke="{color}" stroke-width="{s.width}" stroke-linecap="round"/>'
            )

    # pads + footprint silk
    for fpi in board.placements:
        for pad in fpi.footprint.pads:
            px = fpi.x + pad.x; py = fpi.y + pad.y
            if pad.shape.value == "circle":
                out.append(f'<circle cx="{px}" cy="{py}" r="{pad.width / 2}" '
                           f'fill="#dddd00"/>')
            else:
                out.append(f'<rect x="{px - pad.width / 2}" y="{py - pad.height / 2}" '
                           f'width="{pad.width}" height="{pad.height}" '
                           f'fill="#dddd00"/>')
            if pad.is_through_hole:
                out.append(f'<circle cx="{px}" cy="{py}" r="{pad.drill_diameter / 2}" '
                           f'fill="#222"/>')
        out.append(f'<text x="{fpi.x}" y="{fpi.y - fpi.footprint.courtyard_h / 2 - 0.5}" '
                   f'font-size="1.0" fill="white" text-anchor="middle">{fpi.ref}</text>')

    # vias
    for v in board.vias:
        out.append(f'<circle cx="{v.x}" cy="{v.y}" r="{v.diameter / 2}" fill="#aaaa00"/>')
        out.append(f'<circle cx="{v.x}" cy="{v.y}" r="{v.drill / 2}" fill="#000"/>')

    out.append('</svg>')
    text = "\n".join(out)
    with open(path, "w") as f:
        f.write(text)
    return path
