"""Simple grid-based autorouter.

Uses Lee's algorithm (BFS over a 2D grid) to find the shortest path between
two pads, marking already-used cells as obstacles. This is a teaching/baseline
implementation — production routers use rip-up-and-retry with cost-driven A*
and detour penalties.
"""

from collections import deque
from typing import List, Tuple, Optional

from .trace import Trace


class GridRouter:
    """Lee/Hadlock router on a uniform grid."""

    def __init__(self, board, cell=0.25):
        self.board = board
        self.cell = cell
        self.w = int(board.width / cell) + 1
        self.h = int(board.height / cell) + 1
        # 0 = free, 1 = blocked
        self.grid = [[0] * self.w for _ in range(self.h)]
        self._mark_obstacles()

    def _mark_obstacles(self):
        # mark footprint courtyards (pads + body) as obstacles, except pad center
        for fpi in self.board.placements:
            for pad in fpi.footprint.pads:
                px = fpi.x + pad.x
                py = fpi.y + pad.y
                hw = pad.width / 2 + 0.1
                hh = pad.height / 2 + 0.1
                for ix in range(int((px - hw) / self.cell), int((px + hw) / self.cell) + 1):
                    for iy in range(int((py - hh) / self.cell), int((py + hh) / self.cell) + 1):
                        if 0 <= ix < self.w and 0 <= iy < self.h:
                            self.grid[iy][ix] = 1
                # but keep the very center routable
                ix = int(px / self.cell); iy = int(py / self.cell)
                if 0 <= ix < self.w and 0 <= iy < self.h:
                    self.grid[iy][ix] = 0

    def _bfs(self, start, end):
        if start == end:
            return [start]
        prev = {start: None}
        q = deque([start])
        while q:
            x, y = q.popleft()
            if (x, y) == end:
                # reconstruct
                path = []
                cur = (x, y)
                while cur is not None:
                    path.append(cur)
                    cur = prev[cur]
                return list(reversed(path))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.w and 0 <= ny < self.h):
                    continue
                if (nx, ny) in prev:
                    continue
                # allow end cell even if marked
                if self.grid[ny][nx] == 1 and (nx, ny) != end:
                    continue
                prev[(nx, ny)] = (x, y)
                q.append((nx, ny))
        return None

    def route(self, start_xy, end_xy, net_name):
        sx = int(start_xy[0] / self.cell); sy = int(start_xy[1] / self.cell)
        ex = int(end_xy[0] / self.cell);   ey = int(end_xy[1] / self.cell)
        path = self._bfs((sx, sy), (ex, ey))
        if path is None:
            return None
        # mark cells used
        for (x, y) in path:
            if 0 <= x < self.w and 0 <= y < self.h:
                self.grid[y][x] = 1
        # collapse path into segments (turn points)
        trace = Trace(net=net_name, layer="F.Cu")
        if len(path) < 2:
            return trace
        prev_dir = None
        seg_start = path[0]
        for i in range(1, len(path)):
            dx = path[i][0] - path[i - 1][0]
            dy = path[i][1] - path[i - 1][1]
            d = (dx, dy)
            if prev_dir is not None and d != prev_dir:
                # corner — emit segment
                trace.add_segment(seg_start[0] * self.cell, seg_start[1] * self.cell,
                                  path[i - 1][0] * self.cell, path[i - 1][1] * self.cell)
                seg_start = path[i - 1]
            prev_dir = d
        # final segment
        trace.add_segment(seg_start[0] * self.cell, seg_start[1] * self.cell,
                          path[-1][0] * self.cell, path[-1][1] * self.cell)
        return trace

    def route_netlist(self, ratsnest):
        """Route a list of (net, (x1,y1), (x2,y2)) tuples in order."""
        out = []
        for net, a, b in ratsnest:
            t = self.route(a, b, net)
            if t is not None:
                self.board.traces.append(t)
                out.append(t)
        return out
