# Browser Comparison Agent

A browser-capable agent that compares 5 AI coding tools by free and paid plan details using **Playwright** for real browser automation. Produces a structured comparison table and an interactive HTML replay report showing the full agent run.

## Assignment

**Task:** Compare 5 AI coding tools — GitHub Copilot, Cursor, Windsurf, Replit, Tabnine — by free plan and paid plan.

**Pipeline:** User Goal → Planner → Researcher → Browser Skill → Path Selection → Distiller → QA/Critic → Replay Viewer → Final Comparison Table

## 5-Skill Pipeline

| Step | Skill | What it does |
|------|-------|-------------|
| 1 | **Researcher** | Resolves official pricing-page URLs — no hallucination risk |
| 2 | **Browser Skill** | Playwright Chromium: goto, scroll, click tabs/toggles, extract text, screenshot |
| 3 | **Distiller** | Normalises raw text into canonical schema (`$X/month`, `N/A`) |
| 4 | **QA / Critic** | Validates official domains, completeness, price format, URL match |
| 5 | **Replay Viewer** | Generates `replay_report.html`, `replay_data.json`, CSV, Markdown |

## Browser Path Selection

The agent selects the **cheapest correct path** per tool:

| Path | Strategy | Used? |
|------|----------|-------|
| Extract Static page | `document.body.innerText` + regex — reads JS-rendered page text | **Yes (all 5 tools)** |
| Deterministic CSS selectors | Target specific CSS price elements | No |
| A11y Accessibility tree | Traverse browser accessibility tree | No |
| Vision Set-of-marks | Screenshot + vision LLM | No |
| Gateway Blocked | Navigation failed — record N/A and report | Fallback |

## Tools Compared

| Tool | Pricing URL |
|------|------------|
| GitHub Copilot | `github.com/features/copilot/plans` |
| Cursor | `cursor.com/pricing` |
| Windsurf | `windsurf.com/pricing` |
| Replit | `replit.com/pricing` |
| Tabnine | `tabnine.com/pricing` |

## Browser Actions (≥ 3 per tool)

| Action | Description |
|--------|-------------|
| `goto` | Navigate to the official pricing URL |
| `scroll` | Scroll down to reveal plan cards and tier details |
| `click` | Click plan tabs, billing-period toggles, "see all features" expanders |
| `screenshot` | Capture page state — initial, after interaction, and final |
| `extract` | Collect full `document.body.innerText` for regex price parsing |

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Run

```bash
# Headless (faster, no visible window)
python main.py

# Headed / demo mode (Chromium window visible — use for recording)
python main.py --headed
```

## Outputs

```
browser_comparison_agent/
  replay/
    replay_report.html        <- Self-contained HTML replay viewer (open in browser)
    replay_data.json          <- Full structured replay log
    screenshots/              <- PNG captures per tool (initial, interaction, final)
  outputs/
    final_comparison.csv      <- Comparison table (CSV)
    final_comparison.md       <- Comparison table (Markdown)
```

## Replay Report Sections

The HTML report (`replay_report.html`) contains all 8 required sections:

1. Original user goal
2. Planner DAG (with decision diamond and 5 path branches)
3. Browser path chosen (per-tool, mapped to 5-category taxonomy)
4. Candidate URLs (Researcher output)
5. Browser action log (step, action, target, URL, result, timestamp)
6. Screenshots gallery
7. QA / Critic findings
8. Final comparison table

## Browser Action Log Schema

```json
{
  "step": 1,
  "action": "goto | click | scroll | extract | screenshot | error",
  "target": "description of what was acted on",
  "page": "https://...",
  "result": "success | timeout - partial load | failure: <reason>",
  "timestamp": "2026-06-07T10:00:00+00:00"
}
```

## Replay JSON Schema

```json
{
  "goal": "...",
  "planner_dag": { "nodes": [...], "edges": [...] },
  "candidate_urls": [...],
  "browser_path_chosen": {
    "GitHub Copilot": "Extract Static page",
    "Cursor":         "Extract Static page",
    "Windsurf":       "Extract Static page",
    "Replit":         "Extract Static page",
    "Tabnine":        "Extract Static page"
  },
  "actions": [...],
  "screenshots": [...],
  "extracted_data": [...],
  "qa_findings": [...],
  "final_comparison_table": [...],
  "turn_count": 32,
  "estimated_cost": "N/A",
  "run_start": "...",
  "run_end": "...",
  "duration_seconds": 75.4
}
```

## Comparison Table Columns

`Tool | Free Plan | Paid Plan | Starting Price | Key Features | Source URL | Notes`

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full pipeline diagram, component breakdown, design decisions, and extension points.

## Requirements

- Python 3.10+
- `playwright >= 1.44.0`
- `Pillow >= 10.0.0`
- Chromium (installed via `playwright install chromium`)
