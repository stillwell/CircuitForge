"""Vendor URL resolver.

Given a ComponentRecord (or a dict-shaped equivalent), produce an ordered
list of clickable links to the vendor's product page, datasheet, and
cross-reference search. Used by the REST API (serialized into the
JSON payload), the web portal (icon buttons), the CLI `library show`
command, and the Qt library browser.
"""

import urllib.parse


# Per-source brand metadata. The accent colour is used by the web portal
# for the icon badge; the icon name maps to the SVG file under
# circuitforge/web/static/vendor-icons/<name>.svg.
VENDOR_META = {
    "jlcpcb":    {"label": "JLCPCB",    "color": "#0fa958", "icon": "jlcpcb"},
    "lcsc":      {"label": "LCSC",      "color": "#0fa958", "icon": "lcsc"},
    "digikey":   {"label": "DigiKey",   "color": "#cc0000", "icon": "digikey"},
    "mouser":    {"label": "Mouser",    "color": "#0072ce", "icon": "mouser"},
    "octopart":  {"label": "Octopart",  "color": "#1ec18b", "icon": "octopart"},
    "kicad":     {"label": "KiCad",     "color": "#314cb0", "icon": "kicad"},
    "datasheet": {"label": "Datasheet", "color": "#888888", "icon": "datasheet"},
    "local":     {"label": "Local",     "color": "#666666", "icon": "local"},
}


def _q(s):
    return urllib.parse.quote(str(s), safe="")


def _link(kind, label_suffix, url):
    """Build a single link dict from one of the VENDOR_META entries."""
    meta = VENDOR_META[kind]
    return {
        "kind": kind,
        "label": f"{meta['label']}{label_suffix}",
        "url": url,
        "color": meta["color"],
        "icon": meta["icon"],
    }


def vendor_links(record):
    """Return an ordered list of link dicts for one component record.

    Each dict has keys: kind, label, url, color, icon. Empty list if no
    URL can be derived (e.g. the bundled `local` JSON catalogue with no
    real vendor backing).
    """
    if record is None:
        return []
    # Accept either ComponentRecord or a dict
    def f(name):
        if hasattr(record, name):
            return getattr(record, name) or ""
        return record.get(name, "") or ""

    source = f("source")
    source_id = f("source_id")
    mpn = f("mpn")
    datasheet_url = f("datasheet_url")
    symbol_lib = f("symbol_lib")
    name = f("name")

    out = []

    # 1. Vendor-specific primary product page
    if source == "jlcpcb":
        # source_id looks like "C1234567"; numeric form is the LCSC part #.
        lcsc_num = source_id.lstrip("Cc")
        if lcsc_num:
            out.append(_link("lcsc", " product page",
                             f"https://www.lcsc.com/product-detail/C{lcsc_num}.html"))
            out.append(_link("jlcpcb", " part detail",
                             f"https://jlcpcb.com/partdetail/{lcsc_num}"))
    elif source == "digikey":
        # DigiKey accepts MPN in their /products/result?keywords= URL
        if mpn:
            out.append(_link("digikey", " product page",
                             f"https://www.digikey.com/en/products/result?keywords={_q(mpn)}"))
        elif source_id:
            out.append(_link("digikey", " part",
                             f"https://www.digikey.com/en/products/detail/{_q(source_id)}"))
    elif source == "mouser":
        ref = mpn or source_id
        if ref:
            out.append(_link("mouser", " product page",
                             f"https://www.mouser.com/c/?q={_q(ref)}"))
    elif source == "octopart":
        ref = mpn or name or source_id
        if ref:
            out.append(_link("octopart", " on Octopart",
                             f"https://octopart.com/search?q={_q(ref)}"))
    elif source == "kicad":
        # source_id is "<lib>:<symbol>"
        if symbol_lib or source_id:
            lib = symbol_lib or source_id.split(":", 1)[0]
            out.append(_link("kicad", f" symbol library ({lib})",
                             f"https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/master/{_q(lib)}.kicad_sym"))

    # 2. Datasheet — works for any source that supplies a URL
    if datasheet_url:
        out.append(_link("datasheet", "", datasheet_url))

    # 3. Cross-reference: any record with an MPN gets an Octopart search
    #    button so users can compare prices/stock across distributors.
    if mpn and source != "octopart":
        out.append(_link("octopart", f" search '{mpn}'",
                         f"https://octopart.com/search?q={_q(mpn)}"))

    return out
