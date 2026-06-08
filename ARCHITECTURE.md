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
ResearcherSkill          -- resolves 5 official pricing-page URLs (no network calls)
    |
    v
BrowserSkill             -- Playwright async; one isolated context per tool
    |  goto → screenshot → scroll → click tabs/toggles → extract innerText → screenshot
    v
DistillerSkill           -- normalises raw text into canonical schema ($X/month, N/A)
    |
    v
QASkill                  -- validates official domain, price format, field completeness
    |
    +--------+------------+
    v                     v
replay_report.html    final_comparison.csv / .md
replay_data.json
screenshots/*.png
```

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
- **Extraction path:** `text+heuristic` — collects full `document.body.innerText`,
  then per-tool regex + keyword parsing. Falls back to `N/A` rather than guessing.
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

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Playwright over requests/BeautifulSoup | Pricing pages are JS-rendered; static HTTP cannot see plan cards |
| Async Python | Playwright's native API is async; enables future parallel tool extraction |
| Per-tool `BrowserContext` | Prevents session/cookie bleed between tool visits |
| Text extraction + regex over CSS selectors | Pricing page HTML structure changes frequently; page text is stable |
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
```
goal, planner_dag, candidate_urls, browser_path_chosen,
actions, screenshots, extracted_data, qa_findings,
final_comparison_table, turn_count, estimated_cost,
run_start, run_end, duration_seconds
```

### Comparison table row
```
tool | free_plan | paid_plan | starting_price | key_features | source_url | notes
```

---

## Extension Points

- **Add a tool:** one new dict in `ResearcherSkill.TOOLS` + one parser method in `BrowserSkill`.
- **Add an extraction strategy:** implement a new `_interact_*` method; the dispatcher in
  `_get_extractor()` routes by tool name.
- **Parallel extraction:** replace the sequential `for` loop in `main.py` with
  `asyncio.gather(*[browser_skill.extract_pricing(t) for t in candidate_urls])`.
- **Vision extraction:** replace `innerText` with a screenshot passed to a multimodal LLM.

---

## File Structure

```
browser_comparison_agent/
  main.py                    Orchestrator (5-stage pipeline, CLI flags, output writers)
  requirements.txt
  ARCHITECTURE.md            This file
  skills/
    researcher_skill.py      Official URL catalogue
    browser_skill.py         Playwright automation + per-tool interaction handlers
    distiller_skill.py       Schema normalisation
    qa_skill.py              Source validation and completeness checks
  replay/
    replay_report.html       Self-contained HTML replay viewer
    replay_data.json         Full structured run log
    screenshots/             PNG captures (initial + interaction + final per tool)
  outputs/
    final_comparison.csv
    final_comparison.md
```
