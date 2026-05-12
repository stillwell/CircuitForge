"""SPICE netlist parser and writer.

We accept a useful subset of SPICE2/3 syntax:

    * comment line
    Rxxx n1 n2 value
    Cxxx n1 n2 value [IC=v]
    Lxxx n1 n2 value [IC=i]
    Vxxx n+ n- value | DC value | SIN(...) | PULSE(...) | PWL(...) | AC mag phase
    Ixxx n+ n- value | (same forms)
    Dxxx n+ n- model
    Qxxx nc nb ne model
    Mxxx nd ng ns nb model L=... W=...
    Exxx nout+ nout- nc+ nc- gain    (VCVS)
    Gxxx nout+ nout- nc+ nc- gm      (VCCS)
    Hxxx nout+ nout- vsense gain     (CCVS) — vsense is a V source ref
    Fxxx nout+ nout- vsense gain     (CCCS)
    Xxxx n1 n2 ... subname           (subcircuit instance)
    .model name TYPE(params)
    .subckt name n1 n2 ...
    .ends
    .tran step stop
    .dc src start stop step
    .ac dec n start stop
    .op
    .options ...
    .include "file.lib"
    .end
"""

import re
import os
from circuitforge.core.netlist import Netlist
from circuitforge.core.units import parse_value


def _split_tokens(line):
    return [t for t in re.split(r"\s+", line.strip()) if t]


def parse_spice(text, base_dir=None):
    """Parse a SPICE deck. Returns (Netlist, directives_list)."""
    from circuitforge.components.passive import Resistor, Capacitor, Inductor
    from circuitforge.components.sources import (
        VoltageSource, CurrentSource, SinSource, PulseSource, PWLSource,
        VCVS, VCCS, CCVS, CCCS,
    )
    from circuitforge.components.active import Diode, BJT, MOSFET

    nl = Netlist(name="spice-import")
    lines = text.splitlines()
    # join continuation lines (those starting with '+')
    joined = []
    for ln in lines:
        if ln.startswith("+") and joined:
            joined[-1] += " " + ln[1:].strip()
        else:
            joined.append(ln)

    # first non-blank line is the title
    title_seen = False
    for raw in joined:
        ln = raw.strip()
        if not ln:
            continue
        if not title_seen:
            nl.name = ln
            title_seen = True
            continue
        if ln.startswith("*"):
            continue
        if ln.lower().startswith(".end") and not ln.lower().startswith(".ends"):
            break
        if ln.startswith("."):
            nl.directives.append(ln)
            if ln.lower().startswith(".include"):
                m = re.search(r'\.include\s+"?([^"\s]+)"?', ln, re.IGNORECASE)
                if m and base_dir:
                    inc = os.path.join(base_dir, m.group(1))
                    if os.path.exists(inc):
                        with open(inc) as f:
                            sub_nl, sub_dirs = parse_spice(f.read(), base_dir)
                        for c in sub_nl.components:
                            nl.add(c)
                        nl.directives.extend(sub_dirs)
            continue

        toks = _split_tokens(ln)
        if not toks:
            continue
        ref = toks[0]
        tag = ref[0].upper()

        try:
            if tag == "R" and len(toks) >= 4:
                nl.add(Resistor(ref=ref, value=parse_value(toks[3]),
                                pins=_two(ref, toks[1], toks[2], "1", "2")))
            elif tag == "C" and len(toks) >= 4:
                nl.add(Capacitor(ref=ref, value=parse_value(toks[3]),
                                 pins=_two(ref, toks[1], toks[2], "1", "2")))
            elif tag == "L" and len(toks) >= 4:
                nl.add(Inductor(ref=ref, value=parse_value(toks[3]),
                                pins=_two(ref, toks[1], toks[2], "1", "2")))
            elif tag == "V":
                src = _parse_source(ref, toks, VoltageSource, SinSource, PulseSource, PWLSource)
                nl.add(src)
            elif tag == "I":
                src = _parse_source(ref, toks, CurrentSource, None, None, None)
                nl.add(src)
            elif tag == "D" and len(toks) >= 4:
                nl.add(Diode(ref=ref, value=toks[3],
                             pins=_two(ref, toks[1], toks[2], "A", "K")))
            elif tag == "Q" and len(toks) >= 5:
                nl.add(BJT(ref=ref, value=toks[4],
                           pins=_three(ref, toks[1], toks[2], toks[3], "C", "B", "E")))
            elif tag == "M" and len(toks) >= 6:
                nl.add(MOSFET(ref=ref, value=toks[5],
                              pins=_four(ref, toks[1], toks[2], toks[3], toks[4],
                                         "D", "G", "S", "B")))
            elif tag == "E" and len(toks) >= 6:
                nl.add(VCVS(ref=ref, value=parse_value(toks[5]),
                            pins=_four(ref, toks[1], toks[2], toks[3], toks[4],
                                       "out+", "out-", "in+", "in-")))
            elif tag == "G" and len(toks) >= 6:
                nl.add(VCCS(ref=ref, value=parse_value(toks[5]),
                            pins=_four(ref, toks[1], toks[2], toks[3], toks[4],
                                       "out+", "out-", "in+", "in-")))
            else:
                nl.directives.append(f"# unparsed: {ln}")
        except Exception as e:
            nl.directives.append(f"# parse_error on {ln!r}: {e}")
    return nl, nl.directives


def _two(ref, n1, n2, name1, name2):
    from circuitforge.core.component import Pin
    return [Pin(name=name1, number=1, net=n1), Pin(name=name2, number=2, net=n2)]


def _three(ref, n1, n2, n3, a, b, c):
    from circuitforge.core.component import Pin
    return [Pin(name=a, number=1, net=n1),
            Pin(name=b, number=2, net=n2),
            Pin(name=c, number=3, net=n3)]


def _four(ref, n1, n2, n3, n4, a, b, c, d):
    from circuitforge.core.component import Pin
    return [Pin(name=a, number=1, net=n1),
            Pin(name=b, number=2, net=n2),
            Pin(name=c, number=3, net=n3),
            Pin(name=d, number=4, net=n4)]


def _parse_source(ref, toks, dc_cls, sin_cls, pulse_cls, pwl_cls):
    """Parse a V/I source line into the appropriate source object."""
    pos, neg = toks[1], toks[2]
    rest = " ".join(toks[3:])
    rest_upper = rest.upper()

    if "SIN" in rest_upper and sin_cls:
        m = re.search(r"SIN\s*\(([^)]+)\)", rest, re.IGNORECASE)
        if m:
            args = [parse_value(t) for t in re.split(r"[ ,]+", m.group(1).strip()) if t]
            return sin_cls.from_args(ref, pos, neg, args)
    if "PULSE" in rest_upper and pulse_cls:
        m = re.search(r"PULSE\s*\(([^)]+)\)", rest, re.IGNORECASE)
        if m:
            args = [parse_value(t) for t in re.split(r"[ ,]+", m.group(1).strip()) if t]
            return pulse_cls.from_args(ref, pos, neg, args)
    if "PWL" in rest_upper and pwl_cls:
        m = re.search(r"PWL\s*\(([^)]+)\)", rest, re.IGNORECASE)
        if m:
            args = [parse_value(t) for t in re.split(r"[ ,]+", m.group(1).strip()) if t]
            return pwl_cls.from_args(ref, pos, neg, args)
    # DC fallback: first numeric token
    if rest_upper.startswith("DC"):
        rest = rest.split(None, 1)[1]
    try:
        val = parse_value(rest.split()[0])
    except Exception:
        val = 0.0
    from circuitforge.core.component import Pin
    return dc_cls(ref=ref, value=val, pins=[
        Pin(name="+", number=1, net=pos),
        Pin(name="-", number=2, net=neg),
    ])


def write_spice(netlist, title=None):
    """Serialize a Netlist to a SPICE deck string."""
    lines = [title or netlist.name or "* circuitforge export"]
    for c in netlist.components:
        lines.append(c.to_spice())
    for d in netlist.directives:
        if not d.startswith("#"):
            lines.append(d)
    lines.append(".end")
    return "\n".join(lines) + "\n"
