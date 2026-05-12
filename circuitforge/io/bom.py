"""Bill-of-materials export — CSV and HTML."""

import csv
from collections import defaultdict


def _group(components):
    """Group by (type, value, footprint) → list of refs."""
    groups = defaultdict(list)
    for c in components:
        key = (type(c).__name__, str(c.value), c.footprint or "")
        groups[key].append(c.ref)
    return groups


def write_bom_csv(netlist, path):
    groups = _group(netlist.components)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item", "Quantity", "References", "Type", "Value", "Footprint"])
        for i, ((type_, value, fp), refs) in enumerate(sorted(groups.items()), start=1):
            w.writerow([i, len(refs), ", ".join(sorted(refs)), type_, value, fp])
    return path


def write_bom_html(netlist, path, title="Bill of Materials"):
    groups = _group(netlist.components)
    rows = []
    for i, ((type_, value, fp), refs) in enumerate(sorted(groups.items()), start=1):
        rows.append(
            f"<tr><td>{i}</td><td>{len(refs)}</td>"
            f"<td>{', '.join(sorted(refs))}</td>"
            f"<td>{type_}</td><td>{value}</td><td>{fp}</td></tr>"
        )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: sans-serif; padding: 1em; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #aaa; padding: 0.3em 0.6em; }}
th {{ background: #eee; }}
</style></head><body>
<h1>{title}</h1>
<p>Total parts: {sum(len(r) for r in groups.values())}</p>
<table>
<thead><tr><th>#</th><th>Qty</th><th>Refs</th><th>Type</th><th>Value</th><th>Footprint</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table></body></html>
"""
    with open(path, "w") as f:
        f.write(html)
    return path
