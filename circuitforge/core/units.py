"""SI unit prefix parsing and formatting.

Accepts SPICE-style suffixes (case-insensitive) plus engineering suffixes.
"meg" is megaohms; "m" alone is milli. Matches ngspice behavior.
"""

import re

SI_PREFIXES = {
    "y": 1e-24, "z": 1e-21, "a": 1e-18, "f": 1e-15, "p": 1e-12,
    "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3,
    "":  1.0,
    "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12, "p_big": 1e15,
}

_VALUE_RE = re.compile(
    r"^\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*"
    r"(meg|MEG|Meg|mil|MIL|[yzafpnumµkKMGT])?\s*"
    r"([a-zA-Zµ%/]*)?\s*$"
)


def parse_value(text):
    """Parse a value string like '4.7k', '100nF', '1MEG', '2.2u' to a float.

    Returns the numerical value (units stripped). Raises ValueError on bad input.
    """
    if isinstance(text, (int, float)):
        return float(text)
    if text is None:
        raise ValueError("cannot parse None as a value")
    s = str(text).strip()
    if not s:
        raise ValueError("empty value")
    m = _VALUE_RE.match(s)
    if not m:
        raise ValueError(f"cannot parse value: {text!r}")
    num, suffix, _trailing = m.groups()
    base = float(num)
    if suffix is None or suffix == "":
        return base
    sfx = suffix.lower()
    if sfx == "meg":
        return base * 1e6
    if sfx == "mil":
        return base * 25.4e-6  # mils to meters
    table = {
        "y": 1e-24, "z": 1e-21, "a": 1e-18, "f": 1e-15, "p": 1e-12,
        "n": 1e-9,  "u": 1e-6,  "µ": 1e-6,  "m": 1e-3,
        "k": 1e3,   "g": 1e9,   "t": 1e12,
    }
    # SPICE: uppercase 'M' is mega in some flavors, milli in others.
    # ngspice treats 'M' as milli. We follow ngspice.
    if suffix == "M":
        return base * 1e-3
    if sfx in table:
        return base * table[sfx]
    raise ValueError(f"unknown SI suffix: {suffix!r}")


_ENG_SUFFIXES = [
    (1e12, "T"), (1e9, "G"), (1e6, "Meg"), (1e3, "k"),
    (1.0, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n"),
    (1e-12, "p"), (1e-15, "f"),
]


def format_value(x, precision=3):
    """Format a float in engineering notation with SI suffix."""
    if x == 0:
        return "0"
    ax = abs(x)
    for factor, suffix in _ENG_SUFFIXES:
        if ax >= factor:
            return f"{x / factor:.{precision}g}{suffix}"
    return f"{x:.{precision}g}"
