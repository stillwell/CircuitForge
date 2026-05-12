"""Mouser API loader.

Needs an API key from https://www.mouser.com/api-hub/. Set:

    MOUSER_API_KEY

Mouser allows 30 calls / minute and 1 000 per day on the free tier. We
walk part keywords (configurable via MOUSER_KEYWORDS) and paginate.
"""

import json
import os
import time
import urllib.parse
import urllib.request

from .base import Loader, LoaderError
from ..components_db import ComponentRecord


SEARCH_URL = "https://api.mouser.com/api/v1/search/keyword"


class MouserLoader(Loader):
    name = "mouser"
    description = "Mouser REST API (requires MOUSER_API_KEY)."

    def is_available(self):
        return bool(os.environ.get("MOUSER_API_KEY"))

    def iter_records(self, limit=None):
        key = os.environ["MOUSER_API_KEY"]
        keywords = os.environ.get("MOUSER_KEYWORDS",
                                  "resistor capacitor inductor mosfet op-amp "
                                  "microcontroller diode regulator").split()
        records_per_page = 50
        max_records_per_kw = int(os.environ.get("MOUSER_MAX_RECORDS", "500"))
        emitted = 0
        for kw in keywords:
            start = 0
            while start < max_records_per_kw:
                payload = json.dumps({
                    "SearchByKeywordRequest": {
                        "keyword": kw,
                        "records": records_per_page,
                        "startingRecord": start,
                    }
                }).encode()
                url = f"{SEARCH_URL}?apiKey={urllib.parse.quote(key)}"
                req = urllib.request.Request(url, data=payload, headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": self.user_agent,
                })
                try:
                    with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                        body = json.load(resp)
                except Exception as e:
                    raise LoaderError(f"Mouser API failed for {kw} @{start}: {e}")
                parts = (body.get("SearchResults") or {}).get("Parts") or []
                if not parts:
                    break
                for p in parts:
                    rec = self._parse(p)
                    if rec is not None:
                        yield rec
                        emitted += 1
                        if limit is not None and emitted >= limit:
                            return
                start += records_per_page
                time.sleep(2.1)  # ~30 calls/minute ≤ 0.5 Hz

    def _parse(self, p):
        sid = p.get("MouserPartNumber") or p.get("ManufacturerPartNumber")
        if not sid:
            return None
        return ComponentRecord(
            source=self.name,
            source_id=str(sid),
            mpn=p.get("ManufacturerPartNumber", ""),
            manufacturer=p.get("Manufacturer", ""),
            name=(p.get("Description") or "")[:80],
            description=p.get("Description") or "",
            category=p.get("Category") or "",
            datasheet_url=p.get("DataSheetUrl") or "",
            image_url=p.get("ImagePath") or "",
            stock=int(_parse_int(p.get("AvailabilityInStock", "0"))),
            price_breaks=[{"qty": _parse_int(pb.get("Quantity", "1")),
                           "price": _parse_price(pb.get("Price", "0"))}
                          for pb in (p.get("PriceBreaks") or [])],
            parameters={a.get("AttributeName", str(i)): a.get("AttributeValue")
                        for i, a in enumerate(p.get("ProductAttributes") or [])
                        if isinstance(a, dict)},
        )


def _parse_int(s):
    if isinstance(s, int):
        return s
    try:
        return int("".join(c for c in str(s) if c.isdigit()))
    except ValueError:
        return 0


def _parse_price(s):
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s)
    keep = "".join(c for c in s if c.isdigit() or c == "." or c == "-")
    try:
        return float(keep) if keep else 0.0
    except ValueError:
        return 0.0
