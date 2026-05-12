"""AC small-signal analysis.

For each frequency in the sweep, we build a complex-valued MNA system using
each component's stamp_ac() method. Capacitors stamp jωC, inductors 1/(jωL), etc.
Nonlinear devices are linearized about the DC operating point (TODO: not yet
auto-linearized; small-signal models are user-supplied via their stamp_ac).
"""

import numpy as np
from .mna import MNABuilder


def ac_analysis(netlist, freqs, sweep_type="dec"):
    """Run an AC sweep.

    Parameters
    ----------
    netlist : Netlist
    freqs   : sequence of frequencies (Hz), OR a tuple (start, stop, points)
              if sweep_type is "dec" or "lin".
    sweep_type : "dec" (decade), "lin" (linear), or "list" (use freqs as-is).

    Returns
    -------
    (frequencies, results) where results is a dict {net_name: complex array}.
    """
    # If caller passed an explicit list/array of frequencies, just use them.
    if hasattr(freqs, "__iter__") and not isinstance(freqs, tuple):
        freqs = np.asarray(list(freqs), dtype=float)
    elif sweep_type == "dec":
        f0, f1, pts = freqs
        n_dec = np.log10(f1 / f0)
        freqs = np.logspace(np.log10(f0), np.log10(f1), int(pts * n_dec) + 1)
    elif sweep_type == "lin":
        f0, f1, pts = freqs
        freqs = np.linspace(f0, f1, int(pts))
    else:
        freqs = np.asarray(list(freqs), dtype=float)

    builder = MNABuilder(netlist)
    results = {name: np.zeros(len(freqs), dtype=complex) for name in builder.node_map}

    for i, f in enumerate(freqs):
        omega = 2.0 * np.pi * f
        def cb(ctx, comp):
            comp.stamp_ac(ctx, omega)
        ctx = builder.build(complex_mode=True, callback=cb)
        try:
            sol = np.linalg.solve(ctx.G, ctx.I)
        except np.linalg.LinAlgError:
            sol, *_ = np.linalg.lstsq(ctx.G, ctx.I, rcond=None)
        for name, idx in builder.node_map.items():
            results[name][i] = sol[idx]
    return freqs, results
