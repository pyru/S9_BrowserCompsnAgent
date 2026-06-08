"""
Distiller Skill — normalises raw extracted pricing rows into a consistent schema.

Guarantees:
  • Every row has all 7 required keys.
  • Prices are in canonical "$X/month" format where parseable.
  • Lists are joined with "; " for CSV safety.
  • Missing / empty values are set to "N/A".
"""

import re
from typing import Any, Dict, List


_PRICE_NORM = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*/?\s*(?:mo(?:nth)?|user)?", re.IGNORECASE)
_REQUIRED_KEYS = ["tool", "free_plan", "paid_plan", "starting_price", "key_features", "source_url", "notes"]


class DistillerSkill:

    def normalize(self, raw_rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        result = []
        for row in raw_rows:
            result.append(self._normalize_row(row))
        return result

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key in _REQUIRED_KEYS:
            val = row.get(key, "")
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            val = str(val).strip()
            out[key] = val if val and val.lower() not in ("none", "null") else "N/A"

        # Normalise price format
        price = out.get("starting_price", "N/A")
        if price != "N/A":
            m = _PRICE_NORM.search(price)
            if m:
                out["starting_price"] = f"${m.group(1)}/month"

        # Trim long strings to sane lengths
        out["free_plan"] = out["free_plan"][:300]
        out["paid_plan"] = out["paid_plan"][:200]
        out["key_features"] = out["key_features"][:400]
        out["notes"] = out["notes"][:300]

        return out
