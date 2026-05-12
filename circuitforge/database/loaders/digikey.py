"""DigiKey API loader (OAuth 2.0 client_credentials).

Needs an API account at https://developer.digikey.com/. Set:

    DIGIKEY_CLIENT_ID
    DIGIKEY_CLIENT_SECRET

The flow:
    1. POST /v1/oauth2/token             (client_credentials grant)
    2. Use the access token against /products/v4/search/keyword
       with category / manufacturer filters to enumerate parts.

DigiKey rate-limits to ~1 000 calls / day for free apps; we cap to 100
pages of 50 records by default and let the user override.
"""

import json
import os
import time
import urllib.parse

from .base import Loader, LoaderError
from ..components_db import ComponentRecord


OAUTH_URL = "https://api.digikey.com/v1/oauth2/token"
SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"


class DigiKeyLoader(Loader):
    name = "digikey"
    description = "DigiKey REST API (requires DIGIKEY_CLIENT_ID + DIGIKEY_CLIENT_SECRET)."

    def is_available(self):
        return bool(os.environ.get("DIGIKEY_CLIENT_ID")
                    and os.environ.get("DIGIKEY_CLIENT_SECRET"))

    def _token(self):
        body = urllib.parse.urlencode({
            "client_id": os.environ["DIGIKEY_CLIENT_ID"],
            "client_secret": os.environ["DIGIKEY_CLIENT_SECRET"],
            "grant_type": "client_credentials",
        }).encode()
        raw = self.http_get(OAUTH_URL, headers={
            "Content-Type": "application/x-www-form-urlencoded",
        }, accept="application/json")
        # http_get only does GET; do a manual POST via urllib for the token
        import urllib.request
        req = urllib.request.Request(OAUTH_URL, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
            data = json.load(resp)
        return data["access_token"]

    def iter_records(self, limit=None):
        token = self._token()
        client_id = os.environ["DIGIKEY_CLIENT_ID"]
        keywords = os.environ.get("DIGIKEY_KEYWORDS", "resistor capacitor inductor "
                                  "mosfet op-amp microcontroller").split()
        page_size = 50
        max_pages = int(os.environ.get("DIGIKEY_MAX_PAGES", "100"))
        emitted = 0
        import urllib.request
        for kw in keywords:
            for page in range(max_pages):
                payload = json.dumps({
                    "Keywords": kw,
                    "Limit": page_size,
                    "Offset": page * page_size,
                }).encode()
                req = urllib.request.Request(SEARCH_URL, data=payload, headers={
                    "Authorization": f"Bearer {token}",
                    "X-DIGIKEY-Client-Id": client_id,
                    "X-DIGIKEY-Locale-Site": "US",
                    "X-DIGIKEY-Locale-Language": "en",
                    "X-DIGIKEY-Locale-Currency": "USD",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": self.user_agent,
                })
                try:
                    with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                        body = json.load(resp)
                except Exception as e:
                    raise LoaderError(f"DigiKey API failed for {kw} p{page}: {e}")
                products = body.get("Products", body.get("ExactMatches") or [])
                if not products:
                    break
                for p in products:
                    rec = self._parse_product(p)
                    if rec is not None:
                        yield rec
                        emitted += 1
                        if limit is not None and emitted >= limit:
                            return
                time.sleep(0.5)  # polite throttle

    def _parse_product(self, p):
        if not isinstance(p, dict):
            return None
        sid = (p.get("ProductVariations", [{}])[0].get("DigiKeyProductNumber")
               if p.get("ProductVariations") else
               p.get("DigiKeyPartNumber") or p.get("ManufacturerProductNumber"))
        if not sid:
            return None
        mfr = (p.get("Manufacturer") or {}).get("Name") \
              if isinstance(p.get("Manufacturer"), dict) else p.get("Manufacturer", "")
        category = p.get("Category", {}).get("Name", "") \
                   if isinstance(p.get("Category"), dict) else ""
        return ComponentRecord(
            source=self.name,
            source_id=str(sid),
            mpn=p.get("ManufacturerProductNumber", ""),
            manufacturer=mfr,
            name=(p.get("Description", {}).get("ProductDescription")
                  if isinstance(p.get("Description"), dict)
                  else p.get("ProductDescription", ""))[:80],
            description=(p.get("Description", {}).get("DetailedDescription")
                         if isinstance(p.get("Description"), dict)
                         else p.get("DetailedDescription", "")),
            category=category,
            package="",
            datasheet_url=p.get("DatasheetUrl") or p.get("PrimaryDatasheet") or "",
            image_url=p.get("PhotoUrl") or p.get("PrimaryPhoto") or "",
            stock=int(p.get("QuantityAvailable") or 0),
            price_breaks=[{"qty": pb.get("BreakQuantity"),
                           "price": pb.get("UnitPrice")}
                          for pb in (p.get("StandardPricing") or [])
                          if isinstance(pb, dict)],
            parameters={pa.get("ParameterText", str(i)): pa.get("ValueText")
                        for i, pa in enumerate(p.get("Parameters", []))
                        if isinstance(pa, dict)},
        )
