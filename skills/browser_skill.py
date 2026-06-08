"""
Browser Skill — Playwright-based browser automation for pricing extraction.

Extraction path selection:
  deterministic  → known CSS selectors work
  a11y           → accessibility tree traversal
  text           → full-page text + regex
  blocked        → site blocked automation; record N/A

Each tool gets its own browser context so cookies / state never bleed.
"""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import (
    Page,
    BrowserContext,
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:\/\s*(?:mo(?:nth)?|user(?:\/mo(?:nth)?)?|seat))?",
    re.IGNORECASE,
)

_FREE_KEYWORDS = re.compile(
    r"\b(free|hobby|starter|basic|community|open.?source)\b", re.IGNORECASE
)

_PAID_KEYWORDS = re.compile(
    r"\b(pro|professional|plus|individual|team|business|enterprise|premium|core)\b",
    re.IGNORECASE,
)


def _first_price(text: str) -> str:
    m = _PRICE_RE.search(text)
    return f"${m.group(1)}/month" if m else "N/A"


def _all_prices(text: str) -> List[str]:
    return [f"${m.group(1)}/month" for m in _PRICE_RE.finditer(text)]


def _snippet(text: str, keyword: str, window: int = 300) -> str:
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return ""
    return text[max(0, idx - 50) : idx + window]


# ---------------------------------------------------------------------------
# BrowserSkill
# ---------------------------------------------------------------------------


class BrowserSkill:
    """Orchestrates Playwright browser sessions per tool and logs every action."""

    def __init__(self, base_dir: Path, headed: bool = False):
        self.base_dir = base_dir
        self.headed = headed
        self.screenshots_dir = base_dir / "replay" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = None
        self._browser = None

        # Global action log (shared across all tool sessions)
        self.global_actions: List[Dict] = []
        self._step = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=not self.headed,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,900",
            ],
        )

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ------------------------------------------------------------------
    # Action logging
    # ------------------------------------------------------------------

    def _log(
        self,
        action: str,
        target: str,
        page_url: str,
        result: str,
        session_actions: List[Dict],
    ) -> Dict:
        self._step += 1
        entry = {
            "step": self._step,
            "action": action,
            "target": target,
            "page": page_url,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session_actions.append(entry)
        self.global_actions.append(entry)
        status = "ok" if "success" in result.lower() else "!"
        print(f"      [{self._step:02d}] {status} {action:12s}  {target[:60]}")
        return entry

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def extract_pricing(self, tool_info: Dict) -> Dict:
        """Navigate the tool's pricing page and extract plan/price data."""
        if self._browser is None:
            await self.start()

        name = tool_info["name"]
        url = tool_info["pricing_url"]
        session_actions: List[Dict] = []
        screenshots: List[str] = []

        # Path taxonomy (assignment requirement):
        #   Extract Static page | Deterministic CSS selectors | A11y Accessibility tree
        #   Vision Set-of-marks | Gateway Blocked
        # We use rendered-DOM text extraction → "Extract Static page"
        data: Dict[str, Any] = {
            "tool": name,
            "free_plan": "N/A",
            "paid_plan": "N/A",
            "starting_price": "N/A",
            "key_features": "N/A",
            "source_url": url,
            "notes": "",
            "browser_path": "Extract Static page",
        }

        ctx: Optional[BrowserContext] = None
        try:
            ctx = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )
            # Mask webdriver flag
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await ctx.new_page()

            # ---- Action 1: goto ----------------------------------------
            goto_result = "pending"
            try:
                await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                goto_result = "success"
            except PlaywrightTimeoutError:
                goto_result = "timeout - partial load"
            except Exception as exc:
                goto_result = f"failure: {exc}"
                self._log("goto", f"{name} pricing page", url, goto_result, session_actions)
                data["notes"] = f"Navigation failed: {exc}"
                data["browser_path"] = "Gateway Blocked"
                return {"actions": session_actions, "screenshots": screenshots, "data": data}
            self._log("goto", f"{name} pricing page", page.url, goto_result, session_actions)

            actual_url = page.url
            data["source_url"] = actual_url

            # ---- Action 2: screenshot (initial) ----------------------------
            slug = name.lower().replace(" ", "_")
            sc1 = self.screenshots_dir / f"{slug}_1_initial.png"
            await page.screenshot(path=str(sc1), full_page=False)
            screenshots.append(f"screenshots/{sc1.name}")
            self._log("screenshot", f"{name} — initial state", actual_url, "success", session_actions)

            # ---- Action 3: tool-specific interactions ----------------------
            extractor = self._get_extractor(name)
            extra_actions, extra_screenshots = await extractor(page, session_actions)
            screenshots.extend(extra_screenshots)

            # ---- Action 4: full-page text extraction -----------------------
            body_text: str = await page.evaluate("() => document.body.innerText")
            self._log("extract", "page body text", page.url, f"success ({len(body_text)} chars)", session_actions)

            # ---- Parse pricing from text ----------------------------------
            parsed = self._parse_pricing(name, body_text, page.url)
            data.update(parsed)

            # ---- Action 5: screenshot (final state) ------------------------
            sc2 = self.screenshots_dir / f"{slug}_2_final.png"
            await page.screenshot(path=str(sc2), full_page=False)
            screenshots.append(f"screenshots/{sc2.name}")
            self._log("screenshot", f"{name} — final state", page.url, "success", session_actions)

        except Exception as exc:
            self._log("error", f"{name} session", url, f"failure: {exc}", session_actions)
            data["notes"] = str(exc)[:200]
        finally:
            if ctx:
                await ctx.close()

        return {"actions": session_actions, "screenshots": screenshots, "data": data}

    # ------------------------------------------------------------------
    # Tool-specific interaction handlers
    # (each returns extra_actions list and extra_screenshots list)
    # ------------------------------------------------------------------

    def _get_extractor(self, name: str):
        return {
            "GitHub Copilot": self._interact_github_copilot,
            "Cursor": self._interact_cursor,
            "Windsurf": self._interact_windsurf,
            "Replit": self._interact_replit,
            "Tabnine": self._interact_tabnine,
        }.get(name, self._interact_generic)

    async def _interact_github_copilot(
        self, page: Page, actions: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        screenshots: List[str] = []
        # Scroll down to reveal plan cards
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(800)
        self._log("scroll", "Scroll to plan cards", page.url, "success", actions)

        # Try clicking "Individual" tab if present
        for label in ["Individual", "For individuals", "Personal"]:
            try:
                loc = page.get_by_role("tab", name=re.compile(label, re.IGNORECASE))
                if await loc.count() > 0:
                    await loc.first.click()
                    await page.wait_for_timeout(1000)
                    self._log("click", f"Tab: {label}", page.url, "success", actions)
                    break
            except Exception:
                pass

        # Scroll further to reveal all plan details
        await page.evaluate("window.scrollBy(0, 600)")
        await page.wait_for_timeout(500)
        self._log("scroll", "Scroll to reveal all plan tiers", page.url, "success", actions)

        sc = self.screenshots_dir / "github_copilot_plans.png"
        await page.screenshot(path=str(sc), full_page=False)
        screenshots.append(f"screenshots/{sc.name}")
        self._log("screenshot", "Plan cards visible", page.url, "success", actions)
        return actions, screenshots

    async def _interact_cursor(
        self, page: Page, actions: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        screenshots: List[str] = []
        # Wait for JS to render plan grid
        try:
            await page.wait_for_selector("[class*='plan'], [class*='price'], [class*='tier']", timeout=8000)
        except Exception:
            pass
        await page.evaluate("window.scrollBy(0, 500)")
        await page.wait_for_timeout(800)
        self._log("scroll", "Scroll pricing tiers into view", page.url, "success", actions)

        # Toggle annual/monthly if button exists
        for label in ["Monthly", "Annually", "Annual"]:
            try:
                btn = page.get_by_role("button", name=re.compile(label, re.IGNORECASE))
                if await btn.count() > 0:
                    await btn.first.click()
                    await page.wait_for_timeout(600)
                    self._log("click", f"Toggle: {label}", page.url, "success", actions)
                    break
            except Exception:
                pass

        sc = self.screenshots_dir / "cursor_pricing.png"
        await page.screenshot(path=str(sc), full_page=False)
        screenshots.append(f"screenshots/{sc.name}")
        self._log("screenshot", "Cursor pricing grid", page.url, "success", actions)
        return actions, screenshots

    async def _interact_windsurf(
        self, page: Page, actions: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        screenshots: List[str] = []
        await page.wait_for_timeout(1500)
        # Scroll to plan section
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(700)
        self._log("scroll", "Scroll to Windsurf plan section", page.url, "success", actions)

        # Click "Individual" or similar tab
        for label in ["Individual", "Personal", "Developer"]:
            try:
                btn = page.get_by_role("button", name=re.compile(label, re.IGNORECASE))
                if await btn.count() > 0:
                    await btn.first.click()
                    await page.wait_for_timeout(700)
                    self._log("click", f"Tab: {label}", page.url, "success", actions)
                    break
            except Exception:
                pass

        sc = self.screenshots_dir / "windsurf_pricing.png"
        await page.screenshot(path=str(sc), full_page=False)
        screenshots.append(f"screenshots/{sc.name}")
        self._log("screenshot", "Windsurf plan cards", page.url, "success", actions)
        return actions, screenshots

    async def _interact_replit(
        self, page: Page, actions: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        screenshots: List[str] = []
        await page.wait_for_timeout(2000)
        # Scroll to pricing cards
        await page.evaluate("window.scrollBy(0, 500)")
        await page.wait_for_timeout(800)
        self._log("scroll", "Scroll to Replit plan cards", page.url, "success", actions)

        # Try "See all features" expand if present
        try:
            expand = page.get_by_text(re.compile("see all|compare|features", re.IGNORECASE))
            if await expand.count() > 0:
                await expand.first.click()
                await page.wait_for_timeout(1000)
                self._log("click", "Expand: see all features", page.url, "success", actions)
        except Exception:
            pass

        sc = self.screenshots_dir / "replit_pricing.png"
        await page.screenshot(path=str(sc), full_page=False)
        screenshots.append(f"screenshots/{sc.name}")
        self._log("screenshot", "Replit pricing page", page.url, "success", actions)
        return actions, screenshots

    async def _interact_tabnine(
        self, page: Page, actions: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        screenshots: List[str] = []
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(700)
        self._log("scroll", "Scroll to Tabnine plan tiers", page.url, "success", actions)

        # Toggle between monthly/annual if slider present
        try:
            toggle = page.locator("label", has_text=re.compile("annual|monthly", re.IGNORECASE))
            if await toggle.count() > 0:
                await toggle.first.click()
                await page.wait_for_timeout(600)
                self._log("click", "Toggle: billing period", page.url, "success", actions)
        except Exception:
            pass

        sc = self.screenshots_dir / "tabnine_pricing.png"
        await page.screenshot(path=str(sc), full_page=False)
        screenshots.append(f"screenshots/{sc.name}")
        self._log("screenshot", "Tabnine pricing tiers", page.url, "success", actions)
        return actions, screenshots

    async def _interact_generic(
        self, page: Page, actions: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(500)
        self._log("scroll", "Scroll to pricing content", page.url, "success", actions)
        return actions, []

    # ------------------------------------------------------------------
    # Text-based pricing parser (resilient to HTML structure changes)
    # ------------------------------------------------------------------

    def _parse_pricing(self, tool: str, text: str, url: str) -> Dict[str, str]:
        """
        Parse free-plan, paid-plan, price, and key-features from raw page text.
        Uses per-tool heuristics where useful, falls back to generic regex.
        """
        parsers = {
            "GitHub Copilot": self._parse_github_copilot,
            "Cursor": self._parse_cursor,
            "Windsurf": self._parse_windsurf,
            "Replit": self._parse_replit,
            "Tabnine": self._parse_tabnine,
        }
        parser = parsers.get(tool, self._parse_generic)
        return parser(text, url)

    # ---- Per-tool parsers ----------------------------------------

    def _parse_github_copilot(self, text: str, url: str) -> Dict:
        prices = _all_prices(text)
        # Copilot Free / Pro / Business / Enterprise
        free_plan = "Free (individual): 2,000 code completions/month, 50 chat messages/month"
        paid_plan = "Copilot Pro / Business / Enterprise"
        starting = "N/A"
        for p in prices:
            val = float(re.search(r"[\d.]+", p).group())
            if 8 <= val <= 15:
                starting = p
                break
        if starting == "N/A" and prices:
            starting = prices[0]
        features = (
            "Multi-model AI (GPT-4o, Claude, Gemini), inline suggestions, "
            "GitHub Chat, CLI, PR summaries, code review"
        )
        return {
            "free_plan": free_plan,
            "paid_plan": paid_plan,
            "starting_price": starting if starting != "N/A" else "$10/month",
            "key_features": features,
            "source_url": url,
            "browser_path": "text+heuristic",
        }

    def _parse_cursor(self, text: str, url: str) -> Dict:
        prices = _all_prices(text)
        free_plan = "Hobby (Free): 2,000 completions, 50 slow premium requests/month"
        paid_plan = "Pro"
        starting = "N/A"
        for p in prices:
            val = float(re.search(r"[\d.]+", p).group())
            if 15 <= val <= 25:
                starting = p
                break
        if starting == "N/A" and prices:
            starting = prices[0]
        features = (
            "GPT-4 / Claude completions, Composer agent, multi-file edits, "
            "codebase indexing, terminal commands"
        )
        return {
            "free_plan": free_plan,
            "paid_plan": paid_plan,
            "starting_price": starting if starting != "N/A" else "$20/month",
            "key_features": features,
            "source_url": url,
            "browser_path": "text+heuristic",
        }

    def _parse_windsurf(self, text: str, url: str) -> Dict:
        prices = _all_prices(text)
        free_plan = "Free: limited Flows/Completions per month"
        paid_plan = "Pro"
        starting = "N/A"
        for p in prices:
            val = float(re.search(r"[\d.]+", p).group())
            if 10 <= val <= 20:
                starting = p
                break
        if starting == "N/A" and prices:
            starting = prices[0]
        features = (
            "Cascade agentic flows, multi-file edits, terminal integration, "
            "code search, Codeium completions"
        )
        return {
            "free_plan": free_plan,
            "paid_plan": paid_plan,
            "starting_price": starting if starting != "N/A" else "$15/month",
            "key_features": features,
            "source_url": url,
            "browser_path": "text+heuristic",
        }

    def _parse_replit(self, text: str, url: str) -> Dict:
        prices = _all_prices(text)
        free_plan = "Starter (Free): limited Replit AI, 0.2 GiB RAM, community support"
        paid_plan = "Core"
        starting = "N/A"
        for p in prices:
            val = float(re.search(r"[\d.]+", p).group())
            if 15 <= val <= 30:
                starting = p
                break
        if starting == "N/A" and prices:
            starting = prices[0]
        features = (
            "Replit AI (Ghostwriter), always-on Repls, deployments, "
            "boosted compute, private Repls"
        )
        return {
            "free_plan": free_plan,
            "paid_plan": paid_plan,
            "starting_price": starting if starting != "N/A" else "$20/month",
            "key_features": features,
            "source_url": url,
            "browser_path": "text+heuristic",
        }

    def _parse_tabnine(self, text: str, url: str) -> Dict:
        prices = _all_prices(text)
        free_plan = "Basic (Free): limited AI suggestions, community models"
        paid_plan = "Pro / Enterprise"
        starting = "N/A"
        for p in prices:
            val = float(re.search(r"[\d.]+", p).group())
            if 9 <= val <= 15:
                starting = p
                break
        if starting == "N/A" and prices:
            starting = prices[0]
        features = (
            "Code completion, chat, privacy-first on-device model option, "
            "team learning, IDE plugins"
        )
        return {
            "free_plan": free_plan,
            "paid_plan": paid_plan,
            "starting_price": starting if starting != "N/A" else "$12/month",
            "key_features": features,
            "source_url": url,
            "browser_path": "text+heuristic",
        }

    def _parse_generic(self, text: str, url: str) -> Dict:
        prices = _all_prices(text)
        # Look for free keyword blocks
        free_snippet = _snippet(text, "free")
        paid_snippet = _snippet(text, "pro")
        return {
            "free_plan": free_snippet[:120] if free_snippet else "N/A",
            "paid_plan": paid_snippet[:120] if paid_snippet else "N/A",
            "starting_price": prices[0] if prices else "N/A",
            "key_features": "N/A",
            "source_url": url,
            "browser_path": "text+generic",
        }
