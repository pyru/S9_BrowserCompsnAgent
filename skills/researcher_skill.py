"""
Researcher Skill — returns known official pricing URLs for AI coding tools.
No network calls; URLs are verified official pages sourced before run time.
"""

from typing import List, Dict


class ResearcherSkill:
    """Finds official pricing-page URLs for target AI coding tools."""

    TOOLS: List[Dict] = [
        {
            "name": "GitHub Copilot",
            "pricing_url": "https://github.com/features/copilot/plans",
            "homepage": "https://github.com/features/copilot",
            "official": True,
            "notes": "GitHub's AI coding assistant — Individual/Business/Enterprise tiers",
        },
        {
            "name": "Cursor",
            "pricing_url": "https://www.cursor.com/pricing",
            "homepage": "https://www.cursor.com",
            "official": True,
            "notes": "AI-first code editor with GPT-4 / Claude integration",
        },
        {
            "name": "Windsurf",
            "pricing_url": "https://codeium.com/pricing",
            "homepage": "https://codeium.com",
            "official": True,
            "notes": "Windsurf (by Codeium); agentic AI IDE — pricing at codeium.com/pricing",
        },
        {
            "name": "Replit",
            "pricing_url": "https://replit.com/pricing",
            "homepage": "https://replit.com",
            "official": True,
            "notes": "Cloud-based IDE with AI coding features (Ghostwriter)",
        },
        {
            "name": "Tabnine",
            "pricing_url": "https://www.tabnine.com/pricing",
            "homepage": "https://www.tabnine.com",
            "official": True,
            "notes": "AI code completion with privacy-first, on-device models",
        },
    ]

    def get_candidate_urls(self) -> List[Dict]:
        """Return the list of tools with their official pricing URLs."""
        return [dict(t) for t in self.TOOLS]

    def describe(self) -> str:
        lines = ["Researcher Skill — Official Pricing URLs:"]
        for t in self.TOOLS:
            lines.append(f"  • {t['name']:20s}  {t['pricing_url']}")
        return "\n".join(lines)
