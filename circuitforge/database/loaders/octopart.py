"""Octopart / Nexar GraphQL loader.

Octopart's API is now branded as Nexar. Needs a bearer token from
https://nexar.com/. Set:

    NEXAR_TOKEN

Nexar's free tier allows ~1 000 queries/month. Each query returns up
to 100 parts via the supSearchMpn query.
"""

import json
import os
import time
import urllib.request

from .base import Loader, LoaderError
from ..components_db import ComponentRecord


GRAPHQL_URL = "https://api.nexar.com/graphql/"

QUERY = """
query Search($q: String!, $limit: Int!) {
  supSearchMpn(q: $q, limit: $limit) {
    results {
      part {
        id mpn shortDescription
        manufacturer { name }
        bestImage { url }
        bestDatasheet { url }
        category { name }
        specs { attribute { name } displayValue }
      }
    }
  }
}
"""


class OctopartLoader(Loader):
    name = "octopart"
    description = "Octopart / Nexar GraphQL API (requires NEXAR_TOKEN)."

    def is_available(self):
        return bool(os.environ.get("NEXAR_TOKEN"))

    def iter_records(self, limit=None):
        token = os.environ["NEXAR_TOKEN"]
        keywords = os.environ.get("OCTOPART_KEYWORDS",
                                  "STM32 ESP32 ATmega LM358 NE555 LM7805").split()
        per_query = 100
        emitted = 0
        for kw in keywords:
            payload = json.dumps({
                "query": QUERY,
                "variables": {"q": kw, "limit": per_query},
            }).encode()
            req = urllib.request.Request(GRAPHQL_URL, data=payload, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": self.user_agent,
            })
            try:
                with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                    body = json.load(resp)
            except Exception as e:
                raise LoaderError(f"Nexar query for {kw} failed: {e}")
            for r in ((body.get("data") or {}).get("supSearchMpn") or {}).get("results") or []:
                part = r.get("part") or {}
                pid = part.get("id")
                if not pid:
                    continue
                yield ComponentRecord(
                    source=self.name,
                    source_id=str(pid),
                    mpn=part.get("mpn", ""),
                    manufacturer=(part.get("manufacturer") or {}).get("name", ""),
                    name=(part.get("shortDescription") or "")[:80],
                    description=part.get("shortDescription") or "",
                    category=(part.get("category") or {}).get("name", ""),
                    datasheet_url=(part.get("bestDatasheet") or {}).get("url", ""),
                    image_url=(part.get("bestImage") or {}).get("url", ""),
                    parameters={s["attribute"]["name"]: s["displayValue"]
                                for s in (part.get("specs") or [])
                                if s.get("attribute") and s.get("displayValue")},
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    return
            time.sleep(1.0)
