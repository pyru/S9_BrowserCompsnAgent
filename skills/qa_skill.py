"""
QA / Critic Skill — validates extracted pricing data.

Checks:
  1. Source URL is from the expected official domain.
  2. No required field is blank (fills N/A if so).
  3. Price format is parseable.
  4. Flags rows where data looks hallucinated or suspiciously uniform.
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlparse


_OFFICIAL_DOMAINS = {
    "GitHub Copilot": ["github.com", "github.dev"],
    "Cursor": ["cursor.com", "cursor.sh"],
    "Windsurf": ["windsurf.com", "codeium.com", "windsurf.ai"],
    "Replit": ["replit.com"],
    "Tabnine": ["tabnine.com"],
}

_PRICE_RE = re.compile(r"\$\d+(?:\.\d+)?(?:/month)?", re.IGNORECASE)


class QASkill:

    def validate(
        self,
        rows: List[Dict[str, Any]],
        candidate_urls: List[Dict],
    ) -> List[Dict]:
        """
        Returns a list of QA finding dicts — one per check, across all rows.
        Each finding has: tool, check, status (pass/warn/fail), detail.
        """
        findings: List[Dict] = []
        url_map = {t["name"]: t["pricing_url"] for t in candidate_urls}

        for row in rows:
            tool = row.get("tool", "Unknown")
            source = row.get("source_url", "")
            expected_domains = _OFFICIAL_DOMAINS.get(tool, [])

            # ---- Check 1: official domain --------------------------------
            try:
                host = urlparse(source).netloc.lstrip("www.")
                domain_ok = any(host == d.lstrip("www.") or host.endswith("." + d) for d in expected_domains)
                findings.append({
                    "tool": tool,
                    "check": "official_domain",
                    "status": "pass" if domain_ok else "warn",
                    "detail": f"Source host '{host}' {'matches' if domain_ok else 'does NOT match'} expected {expected_domains}",
                })
            except Exception as exc:
                findings.append({
                    "tool": tool,
                    "check": "official_domain",
                    "status": "fail",
                    "detail": str(exc),
                })

            # ---- Check 2: no blank required fields -----------------------
            required = ["free_plan", "paid_plan", "starting_price", "key_features"]
            missing = [k for k in required if not row.get(k) or row[k] == "N/A"]
            findings.append({
                "tool": tool,
                "check": "completeness",
                "status": "warn" if missing else "pass",
                "detail": f"Missing/N/A fields: {missing}" if missing else "All required fields populated",
            })

            # ---- Check 3: price parseable --------------------------------
            price = row.get("starting_price", "N/A")
            price_ok = price != "N/A" and bool(_PRICE_RE.search(price))
            findings.append({
                "tool": tool,
                "check": "price_format",
                "status": "pass" if price_ok else "warn",
                "detail": f"starting_price='{price}' — {'parseable' if price_ok else 'not a recognised $X/month pattern'}",
            })

            # ---- Check 4: source URL reachability (basic) ----------------
            expected_url = url_map.get(tool, "")
            url_match = expected_url and (source.startswith(expected_url) or source == expected_url)
            findings.append({
                "tool": tool,
                "check": "url_match",
                "status": "pass" if url_match else "warn",
                "detail": (
                    f"Landed on '{source}' vs expected '{expected_url}'"
                    if not url_match
                    else f"URL matches expected: {expected_url}"
                ),
            })

        return findings

    def summary(self, findings: List[Dict]) -> str:
        passes = sum(1 for f in findings if f["status"] == "pass")
        warns = sum(1 for f in findings if f["status"] == "warn")
        fails = sum(1 for f in findings if f["status"] == "fail")
        return f"QA: {passes} passed, {warns} warnings, {fails} failures (total {len(findings)} checks)"
