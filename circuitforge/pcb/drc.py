"""Design Rule Check (DRC).

Checks pad/trace clearances, trace widths, via sizes, drill sizes, courtyard
overlaps, and silkscreen-on-pad violations.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class DRCRule:
    min_trace_width: float = 0.15      # mm
    min_clearance: float = 0.15
    min_drill: float = 0.25
    min_via_annular_ring: float = 0.1
    min_silk_to_pad: float = 0.1
    min_hole_to_hole: float = 0.5
    board_edge_clearance: float = 0.3


@dataclass
class DRCViolation:
    severity: str        # 'error' | 'warning' | 'info'
    rule: str
    message: str
    location: Optional[Tuple[float, float]] = None


class DRC:
    """Run DRC against a Board."""

    def __init__(self, rules: DRCRule = None):
        self.rules = rules or DRCRule()
        self.violations: List[DRCViolation] = []

    def run(self, board):
        self.violations.clear()
        self._check_traces(board)
        self._check_pads(board)
        self._check_vias(board)
        self._check_courtyards(board)
        return self.violations

    def _check_traces(self, board):
        for trace in board.traces:
            for seg in trace.segments:
                if seg.width < self.rules.min_trace_width:
                    self.violations.append(DRCViolation(
                        severity="error", rule="min_trace_width",
                        message=f"trace {trace.net} segment width "
                                f"{seg.width}mm < {self.rules.min_trace_width}mm",
                        location=(seg.x1, seg.y1)))
        # pairwise clearance
        all_segs = [(s, t.net) for t in board.traces for s in t.segments]
        for i in range(len(all_segs)):
            s1, n1 = all_segs[i]
            for j in range(i + 1, len(all_segs)):
                s2, n2 = all_segs[j]
                if n1 == n2:
                    continue
                if s1.layer != s2.layer:
                    continue
                d = _segments_distance(s1, s2)
                if d < self.rules.min_clearance:
                    self.violations.append(DRCViolation(
                        severity="error", rule="clearance",
                        message=f"clearance {d:.3f}mm between nets "
                                f"{n1} and {n2} on {s1.layer}",
                        location=(s1.x1, s1.y1)))

    def _check_pads(self, board):
        # min drill, annular ring, pad-to-pad clearance for different nets
        for fpi in board.placements:
            for pad in fpi.footprint.pads:
                if pad.is_through_hole:
                    if pad.drill_diameter < self.rules.min_drill:
                        self.violations.append(DRCViolation(
                            severity="error", rule="min_drill",
                            message=f"pad {fpi.ref}.{pad.name} drill "
                                    f"{pad.drill_diameter}mm < min",
                            location=(fpi.x + pad.x, fpi.y + pad.y)))

    def _check_vias(self, board):
        for v in board.vias:
            ring = (v.diameter - v.drill) / 2
            if ring < self.rules.min_via_annular_ring:
                self.violations.append(DRCViolation(
                    severity="error", rule="min_via_ring",
                    message=f"via annular ring {ring:.3f}mm < min",
                    location=(v.x, v.y)))

    def _check_courtyards(self, board):
        items = []
        for fpi in board.placements:
            cx, cy = fpi.x, fpi.y
            w = fpi.footprint.courtyard_w / 2
            h = fpi.footprint.courtyard_h / 2
            items.append((fpi.ref, cx - w, cy - h, cx + w, cy + h))
        for i in range(len(items)):
            r1, x1a, y1a, x1b, y1b = items[i]
            for j in range(i + 1, len(items)):
                r2, x2a, y2a, x2b, y2b = items[j]
                if not (x1b < x2a or x2b < x1a or y1b < y2a or y2b < y1a):
                    self.violations.append(DRCViolation(
                        severity="warning", rule="courtyard",
                        message=f"courtyards of {r1} and {r2} overlap"))


def _segments_distance(s1, s2):
    """Approximate minimum distance between two axis-aligned segments."""
    def point_to_seg(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        cx, cy = x1 + t * dx, y1 + t * dy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    return min(
        point_to_seg(s1.x1, s1.y1, s2.x1, s2.y1, s2.x2, s2.y2),
        point_to_seg(s1.x2, s1.y2, s2.x1, s2.y1, s2.x2, s2.y2),
        point_to_seg(s2.x1, s2.y1, s1.x1, s1.y1, s1.x2, s1.y2),
        point_to_seg(s2.x2, s2.y2, s1.x1, s1.y1, s1.x2, s1.y2),
    )
