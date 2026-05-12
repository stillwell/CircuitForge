"""High-level Simulator facade and result container."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import numpy as np

from .dc import dc_operating_point, dc_sweep
from .ac import ac_analysis
from .transient import transient_analysis


@dataclass
class SimulationResult:
    analysis: str
    independent: Optional[np.ndarray] = None       # time or freq axis
    waveforms: Dict[str, np.ndarray] = field(default_factory=dict)
    operating_point: Optional[Dict[str, float]] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def values(self, net_name):
        return self.waveforms.get(net_name)

    def __repr__(self):
        return f"<SimulationResult {self.analysis} nets={list(self.waveforms)[:6]}…>"


class Simulator:
    """Convenience wrapper over the individual analysis functions."""

    def __init__(self, netlist):
        self.netlist = netlist

    def op(self):
        op = dc_operating_point(self.netlist)
        return SimulationResult(analysis="op", operating_point=op)

    def dc(self, source_ref, start, stop, step):
        xs, ops = dc_sweep(self.netlist, source_ref, start, stop, step)
        nets = [n.name for n in self.netlist.non_ground_nodes()]
        waves = {n: np.array([op.get(n, 0.0) for op in ops]) for n in nets}
        return SimulationResult(analysis="dc", independent=np.asarray(xs),
                                waveforms=waves, meta={"source": source_ref})

    def ac(self, f_start, f_stop, points_per_decade=20):
        freqs, results = ac_analysis(self.netlist, (f_start, f_stop, points_per_decade))
        return SimulationResult(analysis="ac", independent=freqs,
                                waveforms=results)

    def tran(self, t_stop, dt, t_start=0.0, method="be", initial=None):
        ts, wf = transient_analysis(self.netlist, t_start, t_stop, dt,
                                    method=method, initial=initial)
        return SimulationResult(analysis="tran", independent=ts, waveforms=wf,
                                meta={"dt": dt, "method": method})
