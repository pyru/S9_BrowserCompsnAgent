# YouTube Demo Script
## "Browser Comparison Agent — AI Coding Tools Pricing"
### Suggested duration: 4–5 minutes

---

## Before you record

1. Open two windows side-by-side: **terminal** (left) + **file explorer / VS Code** (right).
2. Pre-open `replay/replay_report.html` in a browser tab (keep it behind).
3. Zoom terminal font to 16pt so text is legible.
4. Start screen recording (OBS / Windows Game Bar `Win+G`).

---

## [0:00 – 0:30] Introduction

**Say:**
> "Hi, I'm going to demo a browser-automation agent I built that compares
> five AI coding tools — GitHub Copilot, Cursor, Windsurf, Replit, and Tabnine —
> by navigating their live pricing pages with Playwright, extracting plan details,
> and generating a full replay report. This is not passive web scraping —
> the agent actually clicks tabs, scrolls, and interacts with JavaScript-rendered
> content."

**Show:** project folder structure in VS Code or explorer.

---

## [0:30 – 1:00] Architecture walk-through

**Say:**
> "The pipeline has five stages: Researcher finds official URLs,
> the Browser Skill uses Playwright to navigate and interact,
> the Distiller normalises the data, the QA Skill validates sources,
> and finally the Replay Viewer generates the HTML report and CSV table."

**Show:** `ARCHITECTURE.md` — point to the ASCII pipeline diagram.

---

## [1:00 – 2:30] Live run — headed (visible browser) mode

**Type in terminal:**
```
python main.py --headed
```

**Say while it runs:**
> "Notice the `--headed` flag — this makes the Chromium window visible.
> You can watch the agent navigate to GitHub Copilot's pricing page,
> click the Individual tab, scroll down to reveal all plan cards,
> then move to Cursor, Windsurf, Replit, and Tabnine — 32 browser
> actions in total across all five tools."

**Point out** as each tool block prints:
- `ok goto` — navigation succeeded
- `ok click` — tab interaction
- `ok scroll` — page scrolled
- `ok extract` — text pulled
- `ok screenshot` — PNG saved

---

## [2:30 – 3:30] Replay report

**Switch** to the browser tab with `replay_report.html`.

**Say:**
> "Here's the self-contained HTML replay report. At the top is the run summary —
> 32 actions, 15 screenshots, five tools compared in about 75 seconds."

**Scroll through:**
1. **Planner DAG** — "This visualises the five-stage pipeline."
2. **Browser Action Log** — "Every action is timestamped — step, action type,
   target, URL, result, and UTC time."
3. **Screenshots Gallery** — "Here are the live screenshots captured from each
   pricing page — initial state, after tab clicks, and final state."
4. **QA Findings** — "The QA skill checked official domains, price format,
   and field completeness. 17 passed, 3 warnings — one was a domain redirect
   on Windsurf's page which the agent correctly detected and flagged."
5. **Final Comparison Table** — "And here's the comparison — tool, free plan,
   paid plan, starting price, key features, and the source URL for every value."

---

## [3:30 – 4:00] CSV and Markdown outputs

**Switch** to terminal / file explorer.

**Say:**
> "The same table is also saved as a CSV and a Markdown file in the outputs folder."

**Show:** `outputs/final_comparison.csv` open in Excel or Notepad.

---

## [4:00 – 4:30] Closing

**Say:**
> "Everything is reproducible — clone the repo, run three commands,
> and you get the same live browser run against the current pricing pages.
> The full replay JSON log captures the goal, planner DAG, every browser action,
> screenshots, QA findings, and the final table. Links to the GitHub repo and
> replay report are in the description. Thanks for watching."

**Show:** GitHub repo page briefly, then end recording.

---

## Commands to have ready (copy-paste)

```bash
# Setup (first time only)
pip install -r requirements.txt
playwright install chromium

# Normal run (headless)
python main.py

# Demo / recording run (visible browser)
python main.py --headed

# Open replay report
start replay\replay_report.html
```
