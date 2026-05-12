"""Transient (time-domain) analysis.

Uses companion models with the backward Euler method (unconditionally stable,
first-order accurate). Trapezoidal is available via method='trap'. Reactive
elements expose their previous-step state through self._prev_v / self._prev_i.
"""

import numpy as np
from .mna import MNABuilder


def transient_analysis(netlist, t_start, t_stop, dt, method="be",
                       initial=None, progress=None):
    """Run a transient simulation.

    Parameters
    ----------
    netlist : Netlist
    t_start, t_stop : floats (seconds)
    dt : timestep (seconds)
    method : 'be' (backward Euler) or 'trap' (trapezoidal)
    initial : optional dict {net_name: voltage} for initial conditions
    progress : optional callable(fraction, t) for UI hookup

    Returns
    -------
    times : array of timestamps
    waveforms : dict {net_name: array of values}
    """
    builder = MNABuilder(netlist)
    times = np.arange(t_start, t_stop + dt / 2, dt)
    waveforms = {name: np.zeros(len(times)) for name in builder.node_map}

    # init companion state on reactive components
    for c in netlist.components:
        if hasattr(c, "init_transient"):
            c.init_transient(dt, initial or {})

    # initial solution
    size = builder.n_nodes + builder.n_extra
    prev_sol = np.zeros(size)
    if initial:
        for name, v in initial.items():
            if name in builder.node_map:
                prev_sol[builder.node_map[name]] = v

    for i, t in enumerate(times):
        def cb(ctx, comp):
            if hasattr(comp, "stamp_transient_method"):
                comp.stamp_transient_method(ctx, dt, prev_sol, method)
            elif hasattr(comp, "stamp_transient"):
                comp.stamp_transient(ctx, dt, prev_sol)
            else:
                comp.stamp(ctx)
            if hasattr(comp, "update_source"):
                comp.update_source(ctx, t)

        ctx = builder.build(callback=cb)
        try:
            sol = np.linalg.solve(ctx.G, ctx.I)
        except np.linalg.LinAlgError:
            sol, *_ = np.linalg.lstsq(ctx.G, ctx.I, rcond=None)

        # store
        for name, idx in builder.node_map.items():
            waveforms[name][i] = sol[idx].real

        # let reactive elements update internal state for next step
        for c in netlist.components:
            if hasattr(c, "advance_transient"):
                c.advance_transient(sol, builder.node_map, dt)

        prev_sol = sol
        if progress is not None and (i % max(1, len(times) // 100) == 0):
            progress(i / len(times), t)

    return times, waveforms
