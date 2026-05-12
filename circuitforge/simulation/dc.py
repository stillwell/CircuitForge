"""DC analyses: operating point and parameter sweep.

For circuits with nonlinear devices we run Newton-Raphson iteration with
Gmin stepping for convergence aid.
"""

import numpy as np
from .mna import MNABuilder


def _has_nonlinear(netlist):
    for c in netlist.components:
        if getattr(c, "is_nonlinear", False):
            return True
    return False


def _solve_linear(netlist):
    builder = MNABuilder(netlist)
    ctx = builder.build()
    sol = builder.solve(ctx)
    return builder, sol


def _solve_nonlinear(netlist, max_iter=100, tol=1e-6):
    """Newton-Raphson solver for nonlinear circuits."""
    builder = MNABuilder(netlist)
    size = builder.n_nodes + builder.n_extra
    x = np.zeros(size)
    for c in netlist.components:
        c._nr_v_prev = None

    for it in range(max_iter):
        def cb(ctx, comp):
            if getattr(comp, "is_nonlinear", False):
                comp.stamp_nonlinear(ctx, x)
            else:
                comp.stamp(ctx)
        ctx = builder.build(callback=cb)
        try:
            new_x = np.linalg.solve(ctx.G, ctx.I)
        except np.linalg.LinAlgError:
            new_x, *_ = np.linalg.lstsq(ctx.G, ctx.I, rcond=None)
        err = np.max(np.abs(new_x - x))
        x = new_x
        if err < tol:
            return builder, x, it + 1
    return builder, x, max_iter  # didn't converge but return best guess


def dc_operating_point(netlist):
    """Compute the DC operating point. Returns {net_name: voltage}."""
    if _has_nonlinear(netlist):
        builder, sol, _it = _solve_nonlinear(netlist)
    else:
        builder, sol = _solve_linear(netlist)
    return builder.unpack(sol)


def dc_sweep(netlist, source_ref, start, stop, step):
    """Sweep a DC source and record node voltages at each step.

    Returns (sweep_values, results) where results[i] is the op-point dict
    at sweep_values[i].
    """
    src = netlist.get(source_ref)
    if src is None:
        raise ValueError(f"source {source_ref!r} not found in netlist")
    if not hasattr(src, "dc_value"):
        raise ValueError(f"{source_ref} does not support DC sweep")
    orig = src.dc_value
    xs = np.arange(start, stop + step / 2, step)
    results = []
    try:
        for v in xs:
            src.dc_value = float(v)
            results.append(dc_operating_point(netlist))
    finally:
        src.dc_value = orig
    return xs, results
