"""Command-line interface for CircuitForge.

Examples
--------

    # Run a transient simulation on a SPICE deck:
    python -m circuitforge.cli simulate examples/rc_lowpass.cir \
        --transient 0 10m 10u --probe Vout

    # Convert a SPICE deck to KiCAD schematic (best effort):
    python -m circuitforge.cli convert in.cir --to kicad-sch -o out.kicad_sch

    # Export Gerber files for a board file:
    python -m circuitforge.cli gerber board.kicad_pcb -o gerbers/

    # Run DRC:
    python -m circuitforge.cli drc board.kicad_pcb

    # Generate a BOM:
    python -m circuitforge.cli bom in.cir -o bom.csv

    # Launch GUI:
    python -m circuitforge.cli gui
"""

import argparse
import os
import sys


def main(argv=None):
    from circuitforge import (__version__, __copyright__, __author__,
                              __email__, show_w, show_c, SHORT_NOTICE)
    parser = argparse.ArgumentParser(prog="circuitforge", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version",
                        version=f"CircuitForge {__version__}\n"
                                f"{__copyright__}\n"
                                f"Author: {__author__} <{__email__}>\n"
                                f"License: GPL-3.0-or-later (see LICENSE)")
    parser.add_argument("--show-w", action="store_true",
                        help="Show the GPL warranty disclaimer and exit")
    parser.add_argument("--show-c", action="store_true",
                        help="Show the GPL redistribution conditions and exit")
    parser.add_argument("--license", action="store_true",
                        help="Show the short copyright notice and exit")

    # Handle the early-exit informational flags before requiring a subcommand.
    if argv is not None:
        early = argv
    else:
        early = sys.argv[1:]
    if "--show-w" in early:
        print(show_w()); return 0
    if "--show-c" in early:
        print(show_c()); return 0
    if "--license" in early:
        print(SHORT_NOTICE); return 0

    sub = parser.add_subparsers(dest="command", required=True)

    p_sim = sub.add_parser("simulate", help="Run a SPICE simulation")
    p_sim.add_argument("netlist", help="SPICE netlist (.cir/.sp/.net)")
    p_sim.add_argument("--op", action="store_true", help="DC operating point")
    p_sim.add_argument("--dc", nargs=4, metavar=("SRC", "START", "STOP", "STEP"),
                       help="DC sweep")
    p_sim.add_argument("--ac", nargs=3, metavar=("FSTART", "FSTOP", "PTS_PER_DEC"),
                       help="AC sweep (logarithmic)")
    p_sim.add_argument("--transient", "--tran", nargs=3,
                       metavar=("TSTART", "TSTOP", "DT"),
                       help="Transient analysis")
    p_sim.add_argument("--probe", action="append", default=[],
                       help="Net to print (repeatable)")
    p_sim.add_argument("-o", "--output", help="Write results CSV to this path")

    p_conv = sub.add_parser("convert", help="Convert between formats")
    p_conv.add_argument("input")
    p_conv.add_argument("--to", required=True,
                        choices=["kicad-sch", "kicad-pcb", "spice", "svg", "bom"])
    p_conv.add_argument("-o", "--output", required=True)

    p_ger = sub.add_parser("gerber", help="Write Gerber set from a board file")
    p_ger.add_argument("input")
    p_ger.add_argument("-o", "--output", required=True, help="Output directory")

    p_drl = sub.add_parser("drill", help="Write Excellon drill file")
    p_drl.add_argument("input")
    p_drl.add_argument("-o", "--output", required=True)

    p_drc = sub.add_parser("drc", help="Run design-rule check on a board")
    p_drc.add_argument("input")

    p_bom = sub.add_parser("bom", help="Generate a BOM from a netlist or SPICE deck")
    p_bom.add_argument("input")
    p_bom.add_argument("-o", "--output", required=True)

    p_lib = sub.add_parser("library", help="Inspect the component library")
    p_lib.add_argument("query", nargs="?", default="")

    p_gui = sub.add_parser("gui", help="Launch GUI")

    args = parser.parse_args(argv)
    return dispatch(args)


def dispatch(args):
    cmd = args.command
    if cmd == "simulate":  return _cmd_simulate(args)
    if cmd == "convert":   return _cmd_convert(args)
    if cmd == "gerber":    return _cmd_gerber(args)
    if cmd == "drill":     return _cmd_drill(args)
    if cmd == "drc":       return _cmd_drc(args)
    if cmd == "bom":       return _cmd_bom(args)
    if cmd == "library":   return _cmd_library(args)
    if cmd == "gui":       return _cmd_gui(args)
    return 2


def _cmd_simulate(args):
    from circuitforge.io import read_spice_deck
    from circuitforge.simulation import Simulator
    nl, _ = read_spice_deck(args.netlist)
    print(nl.summary())
    sim = Simulator(nl)
    result = None
    if args.op or not (args.dc or args.ac or args.transient):
        result = sim.op()
        print("DC operating point:")
        for k, v in sorted(result.operating_point.items()):
            print(f"  V({k}) = {v:.6g} V")
    if args.dc:
        src, start, stop, step = args.dc
        from circuitforge.core.units import parse_value
        result = sim.dc(src, parse_value(start), parse_value(stop), parse_value(step))
        _print_summary(result, args.probe)
    if args.ac:
        f0, f1, ppd = args.ac
        from circuitforge.core.units import parse_value
        result = sim.ac(parse_value(f0), parse_value(f1), int(ppd))
        _print_summary(result, args.probe)
    if args.transient:
        t0, t1, dt = args.transient
        from circuitforge.core.units import parse_value
        result = sim.tran(parse_value(t1), parse_value(dt), parse_value(t0))
        _print_summary(result, args.probe)
    if args.output and result is not None:
        _write_csv(result, args.output)
        print(f"Wrote results to {args.output}")
    return 0


def _print_summary(result, probes):
    print(f"Analysis: {result.analysis}")
    if result.independent is not None:
        print(f"  Points: {len(result.independent)}")
    for net in probes or list(result.waveforms)[:4]:
        wave = result.waveforms.get(net)
        if wave is None:
            print(f"  (no such net: {net})")
            continue
        import numpy as np
        peak = np.max(np.abs(getattr(wave, "real", wave)))
        print(f"  V({net})  peak = {peak:.6g}")


def _write_csv(result, path):
    import csv
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        nets = sorted(result.waveforms)
        header = ["t" if result.analysis == "tran" else
                  "f" if result.analysis == "ac" else "x"] + nets
        w.writerow(header)
        ind = result.independent
        for i, x in enumerate(ind):
            row = [x] + [getattr(result.waveforms[n][i], "real",
                                 result.waveforms[n][i]) for n in nets]
            w.writerow(row)


def _cmd_convert(args):
    from circuitforge.io import (read_spice_deck, write_spice_deck,
                                 write_kicad_sch, write_kicad_pcb,
                                 write_bom_csv, export_schematic_svg)
    ext = os.path.splitext(args.input)[1].lower()
    if ext in (".cir", ".sp", ".net"):
        nl, _ = read_spice_deck(args.input)
        if args.to == "spice":
            write_spice_deck(nl, args.output)
        elif args.to == "bom":
            write_bom_csv(nl, args.output)
        else:
            print(f"Conversion from SPICE to {args.to} not supported.")
            return 1
    else:
        print(f"Unsupported input format: {ext}")
        return 1
    print(f"Wrote {args.output}")
    return 0


def _cmd_gerber(args):
    from circuitforge.io import read_kicad_pcb, write_gerber_set
    board = read_kicad_pcb(args.input)
    paths = write_gerber_set(board, args.output)
    print(f"Wrote {len(paths)} Gerber files to {args.output}")
    return 0


def _cmd_drill(args):
    from circuitforge.io import read_kicad_pcb, write_excellon
    board = read_kicad_pcb(args.input)
    write_excellon(board, args.output)
    print(f"Wrote drill file to {args.output}")
    return 0


def _cmd_drc(args):
    from circuitforge.io import read_kicad_pcb
    from circuitforge.pcb import DRC
    board = read_kicad_pcb(args.input)
    drc = DRC()
    violations = drc.run(board)
    if not violations:
        print("DRC: no violations.")
        return 0
    for v in violations:
        loc = f" at {v.location}" if v.location else ""
        print(f"[{v.severity}] {v.rule}: {v.message}{loc}")
    return 1


def _cmd_bom(args):
    from circuitforge.io import read_spice_deck, write_bom_csv, write_bom_html
    nl, _ = read_spice_deck(args.input)
    if args.output.endswith(".html"):
        write_bom_html(nl, args.output)
    else:
        write_bom_csv(nl, args.output)
    print(f"Wrote BOM to {args.output}")
    return 0


def _cmd_library(args):
    from circuitforge.components.library import ComponentLibrary
    lib = ComponentLibrary().load_default()
    entries = lib.search(args.query) if args.query else list(lib)
    if not entries:
        print("(no matches)")
        return 1
    for e in sorted(entries, key=lambda x: (x.kind, x.name)):
        print(f"  {e.kind:14s} {e.name:24s} {e.description}")
    print(f"Total: {len(entries)} of {len(lib)}")
    return 0


def _cmd_gui(args):
    from circuitforge.app import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
