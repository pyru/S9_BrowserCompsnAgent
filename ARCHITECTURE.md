# Architecture Note — Browser Comparison Agent

## Goal

Demonstrate browser automation that passive web search cannot do:
interact with JavaScript-rendered pricing pages (tabs, toggles, scrolling,
dynamic card reveals) and produce a verifiable, replayable run record.

---

## Pipeline (Planner DAG)

```
User Goal
    |
    v
Planner                  -- interprets goal, sequences skills
    |
    v
ResearcherSkill          -- resolves 5 official pricing-page URLs (no network calls)
    |
    v
BrowserSkill             -- Playwright async; one isolated context per tool
    |  goto -> screenshot -> scroll -> click tabs/toggles -> extract innerText -> screenshot
    |
    v
+---------------------------+
|  Cheapest correct path?   |  <-- decision diamond
+---------------------------+
    |         |         |         |         |
    v         v         v         v         v
Extract   Determin-   A11y      Vision   Gateway
Static    istic CSS   Access.   Set-of-  Blocked
page      selectors   tree      marks    (report)
    |         |         |         |         |
    +----+----+---------+---------+---------+
         |
         v
    DistillerSkill       -- normalises raw text into canonical schema ($X/month, N/A)
         |
         v
    QASkill              -- validates official domain, price format, field completeness
         |
    +----+----+
    v         v
replay_    final_comparison
report     .csv / .md
.html
replay_
data.json
screenshots/
```

**Path chosen this run:** `Extract Static page` for all 5 tools
(rendered DOM text via `document.body.innerText` + regex — cheapest path that works)

---

## Component Breakdown

### ResearcherSkill (`skills/researcher_skill.py`)
- Maintains a curated table of official pricing URLs (no hallucination risk).
- Returns a typed list of `{name, pricing_url, homepage, notes}` dicts.
- Easily extended: add a new dict entry to compare more tools.

### BrowserSkill (`skills/browser_skill.py`)
- Uses **Playwright async API** with Chromium.
- Each tool gets its own `BrowserContext` (isolated cookies/storage).
- Masks `navigator.webdriver` to reduce bot-detection rejections.
- **Action types logged:** `goto`, `scroll`, `click`, `extract`, `screenshot`, `error`.
- **Path selection:** selects `Extract Static page` (innerText + regex) as the cheapest
  correct path. Falls back to `Gateway Blocked` if navigation fails entirely.
- **Extraction:** collects full `document.body.innerText`, then per-tool regex + keyword
  parsing. Falls back to `N/A` rather than guessing.
- Supports `--headed` flag for visible demo recording.

### DistillerSkill (`skills/distiller_skill.py`)
- Guarantees all 7 output keys exist on every row.
- Normalises price strings to `$X/month` via regex.
- Joins list values with `"; "` for CSV safety.
- Truncates fields to sane lengths.

### QASkill (`skills/qa_skill.py`)
- Per-row checks: official domain match, completeness, price parseability, URL match.
- Emits `pass / warn / fail` findings — surfaced in both the JSON log and HTML report.
- Flags redirects or unexpected landing domains as warnings.

---

## Browser Path Taxonomy

The agent selects the cheapest path that correctly extracts data:

| Path | Strategy | Cost |
|------|----------|------|
| **Extract Static page** | `document.body.innerText` + regex on JS-rendered DOM | Lowest |
| Deterministic CSS selectors | Target specific CSS price/plan elements | Low |
| A11y Accessibility tree | Traverse browser accessibility tree by ARIA roles | Medium |
| Vision Set-of-marks | Screenshot + vision LLM with bounding-box marks | High |
| Gateway Blocked | Navigation failed — record N/A, log block | N/A |

All 5 tools used **Extract Static page** in this run. The path is recorded
per-tool in `replay_data.json` under `browser_path_chosen`.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Playwright over requests/BeautifulSoup | Pricing pages are JS-rendered; static HTTP cannot see plan cards |
| Async Python | Playwright's native API is async; enables future parallel tool extraction |
| Per-tool `BrowserContext` | Prevents session/cookie bleed between tool visits |
| Text extraction + regex over CSS selectors | Pricing page HTML structure changes frequently; page text is stable |
| 5-path taxonomy in DAG | Assignment requirement; makes path choice explicit and auditable |
| Per-tool `browser_path_chosen` dict | Grader can see exactly which path was used for each tool |
| `N/A` instead of inference | Assignment constraint: no hallucinated pricing |
| Self-contained HTML report | Single file, no server needed — open directly in a browser |
| `--headed` flag | Lets the grader/demo recorder see the live browser without code changes |

---

## Data Schemas

### Browser Action Log entry
```json
{
  "step": 1,
  "action": "goto | scroll | click | extract | screenshot | error",
  "target": "human-readable description",
  "page": "https://...",
  "result": "success | timeout - partial load | failure: <reason>",
  "timestamp": "2026-06-07T10:00:00+00:00"
}
```

### Replay JSON (top-level keys)
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

### Comparison table row
```
tool | free_plan | paid_plan | starting_price | key_features | source_url | notes
```

---

## Replay Report Sections (HTML)

The self-contained `replay_report.html` contains all 8 required assignment sections:

1. Original user goal
2. Planner DAG (with decision diamond and 5 path branches)
3. Browser path chosen (per-tool table, 5-category taxonomy)
4. Candidate URLs (Researcher output)
5. Browser action log (step, action, target, URL, result, timestamp)
6. Screenshots gallery
7. QA / Critic findings
8. Final comparison table

---

## Extension Points

- **Add a tool:** one new dict in `ResearcherSkill.TOOLS` + one parser method in `BrowserSkill`.
- **Add an extraction strategy:** implement a new `_interact_*` method; the dispatcher in
  `_get_extractor()` routes by tool name.
- **Switch to CSS path:** replace `innerText` extraction with `page.query_selector_all()`
  targeting known price card selectors; update `browser_path` to `"Deterministic CSS selectors"`.
- **Switch to Vision path:** pass screenshot to a multimodal LLM; update `browser_path` to
  `"Vision Set-of-marks"`.
- **Parallel extraction:** replace the sequential `for` loop in `main.py` with
  `asyncio.gather(*[browser_skill.extract_pricing(t) for t in candidate_urls])`.

---

## File Structure

```
browser_comparison_agent/
  main.py                    Orchestrator (5-stage pipeline, CLI flags, output writers)
  requirements.txt
  ARCHITECTURE.md            This file
  README.md                  Setup, run commands, schemas, output reference
  DEMO_SCRIPT.md             Timestamped YouTube narration script
  skills/
    researcher_skill.py      Official URL catalogue
    browser_skill.py         Playwright automation + per-tool interaction handlers
    distiller_skill.py       Schema normalisation
    qa_skill.py              Source validation and completeness checks
  replay/
    replay_report.html       Self-contained HTML replay viewer (8 required sections)
    replay_data.json         Full structured run log
    screenshots/             PNG captures (initial + interaction + final per tool)
  outputs/
    final_comparison.csv
    final_comparison.md
```
