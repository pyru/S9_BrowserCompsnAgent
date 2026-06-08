"""
AI Coding Tools Comparison Agent — main orchestrator.

Pipeline:
  User Goal → Researcher → Browser Skill → Distiller → QA → Replay + Outputs

Usage:
  pip install -r requirements.txt
  playwright install
  python main.py
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output so Unicode in extracted page text doesn't crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -- Path setup ----------------------------------------------------------------
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from skills.researcher_skill import ResearcherSkill
from skills.browser_skill import BrowserSkill
from skills.distiller_skill import DistillerSkill
from skills.qa_skill import QASkill

# -- Constants -----------------------------------------------------------------
GOAL = (
    "Compare 5 AI coding tools — GitHub Copilot, Cursor, Windsurf, Replit, Tabnine — "
    "by free-plan details, paid-plan details, and starting price, using live browser "
    "automation on each tool's official pricing page."
)

PLANNER_DAG = {
    "goal": GOAL,
    "nodes": [
        {"id": "user_goal",    "label": "User Goal",                          "type": "input",    "order": 0},
        {"id": "planner",      "label": "Planner",                            "type": "skill",    "order": 1},
        {"id": "researcher",   "label": "Researcher: Find Candidate URLs",    "type": "skill",    "order": 2},
        {"id": "browser",      "label": "Browser Skill: Interact with website","type": "skill",   "order": 3},
        {"id": "path_select",  "label": "Cheapest correct path?",             "type": "decision", "order": 4},
        {"id": "path_extract", "label": "Extract Static page",                "type": "path",     "order": 5},
        {"id": "path_css",     "label": "Deterministic CSS selectors",        "type": "path",     "order": 5},
        {"id": "path_a11y",    "label": "A11y Accessibility tree",            "type": "path",     "order": 5},
        {"id": "path_vision",  "label": "Vision Set-of-marks",               "type": "path",     "order": 5},
        {"id": "path_blocked", "label": "Gateway Blocked: Recover or report", "type": "path",     "order": 5},
        {"id": "distiller",    "label": "Distiller: Normalize Data",          "type": "skill",    "order": 6},
        {"id": "qa",           "label": "QA / Critic: Validate Sources",      "type": "skill",    "order": 7},
        {"id": "replay",       "label": "Replay Viewer: HTML Report",         "type": "output",   "order": 8},
        {"id": "outputs",      "label": "Final Comparison Table",             "type": "output",   "order": 8},
    ],
    "edges": [
        {"from": "user_goal",    "to": "planner"},
        {"from": "planner",      "to": "researcher"},
        {"from": "researcher",   "to": "browser"},
        {"from": "browser",      "to": "path_select"},
        {"from": "path_select",  "to": "path_extract"},
        {"from": "path_select",  "to": "path_css"},
        {"from": "path_select",  "to": "path_a11y"},
        {"from": "path_select",  "to": "path_vision"},
        {"from": "path_select",  "to": "path_blocked"},
        {"from": "path_extract", "to": "distiller"},
        {"from": "path_css",     "to": "distiller"},
        {"from": "path_a11y",    "to": "distiller"},
        {"from": "path_vision",  "to": "distiller"},
        {"from": "path_blocked", "to": "distiller"},
        {"from": "distiller",    "to": "qa"},
        {"from": "qa",           "to": "replay"},
        {"from": "qa",           "to": "outputs"},
    ],
}

# -- Entry point ---------------------------------------------------------------

async def main(headed: bool = False) -> None:
    run_start = datetime.now(timezone.utc)

    (BASE_DIR / "replay" / "screenshots").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "outputs").mkdir(parents=True, exist_ok=True)

    _banner("AI Coding Tools Comparison Agent")
    if headed:
        print("  [DEMO MODE] Browser window will be visible")
    print(f"  Goal: {GOAL}\n")

    # -- 1. Researcher ---------------------------------------------------------
    _section("1/5", "Researcher — finding official pricing URLs")
    researcher = ResearcherSkill()
    candidate_urls = researcher.get_candidate_urls()
    for t in candidate_urls:
        print(f"    • {t['name']:20s}  {t['pricing_url']}")

    # -- 2. Browser Skill ------------------------------------------------------
    _section("2/5", "Browser Skill — navigating pricing pages with Playwright")
    browser_skill = BrowserSkill(BASE_DIR, headed=headed)

    all_actions: list = []
    all_screenshots: list = []
    extracted_data: list = []

    for tool_info in candidate_urls:
        print(f"\n  ► {tool_info['name']}")
        result = await browser_skill.extract_pricing(tool_info)
        all_actions.extend(result.get("actions", []))
        all_screenshots.extend(result.get("screenshots", []))
        extracted_data.append(result.get("data", {}))

    await browser_skill.close()
    print(f"\n  Total browser actions logged: {len(all_actions)}")
    print(f"  Screenshots captured:         {len(all_screenshots)}")

    # -- 3. Distiller ----------------------------------------------------------
    _section("3/5", "Distiller — normalising pricing data")
    distiller = DistillerSkill()
    normalized = distiller.normalize(extracted_data)
    print(f"  Normalised {len(normalized)} tool records")

    # -- 4. QA -----------------------------------------------------------------
    _section("4/5", "QA / Critic — validating sources and completeness")
    qa = QASkill()
    qa_findings = qa.validate(normalized, candidate_urls)
    print(f"  {qa.summary(qa_findings)}")

    # -- 5. Generate outputs ---------------------------------------------------
    _section("5/5", "Generating replay report and comparison tables")
    run_end = datetime.now(timezone.utc)

    # Build per-tool browser path map (uses assignment taxonomy)
    per_tool_paths = {
        d.get("tool", "unknown"): d.get("browser_path", "Extract Static page")
        for d in extracted_data
    }

    replay_data = {
        "goal": GOAL,
        "planner_dag": PLANNER_DAG,
        "candidate_urls": candidate_urls,
        "browser_path_chosen": per_tool_paths,
        "actions": all_actions,
        "screenshots": all_screenshots,
        "extracted_data": extracted_data,
        "qa_findings": qa_findings,
        "final_comparison_table": normalized,
        "turn_count": len(all_actions),
        "estimated_cost": "N/A",
        "run_start": run_start.isoformat(),
        "run_end": run_end.isoformat(),
        "duration_seconds": round((run_end - run_start).total_seconds(), 1),
    }

    # Replay JSON
    replay_json = BASE_DIR / "replay" / "replay_data.json"
    replay_json.write_text(json.dumps(replay_data, indent=2, default=str), encoding="utf-8")

    # CSV
    csv_path = BASE_DIR / "outputs" / "final_comparison.csv"
    _save_csv(normalized, csv_path)

    # Markdown
    md_path = BASE_DIR / "outputs" / "final_comparison.md"
    _save_markdown(normalized, md_path)

    # HTML replay report
    html_path = BASE_DIR / "replay" / "replay_report.html"
    _generate_html(replay_data, html_path)

    # -- Summary ---------------------------------------------------------------
    _banner("Run Complete")
    print(f"  Replay JSON  : {replay_json}")
    print(f"  Replay HTML  : {html_path}")
    print(f"  CSV table    : {csv_path}")
    print(f"  Markdown     : {md_path}")
    print(f"  Screenshots  : {BASE_DIR / 'replay' / 'screenshots'}")
    print(f"  Duration     : {replay_data['duration_seconds']}s")
    print()
    _print_table(normalized)


# -- Output helpers ------------------------------------------------------------

def _save_csv(rows: list, path: Path) -> None:
    keys = ["tool", "free_plan", "paid_plan", "starting_price", "key_features", "source_url", "notes"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "N/A") for k in keys})


def _save_markdown(rows: list, path: Path) -> None:
    headers = ["Tool", "Free Plan", "Paid Plan", "Starting Price", "Key Features", "Source URL", "Notes"]
    keys    = ["tool", "free_plan", "paid_plan", "starting_price", "key_features", "source_url", "notes"]
    lines = [
        "# AI Coding Tools Pricing Comparison\n",
        f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        cells = [str(row.get(k, "N/A")).replace("|", "\\|").replace("\n", " ") for k in keys]
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def _print_table(rows: list) -> None:
    print("  Final Comparison Table")
    print("  " + "-" * 90)
    for row in rows:
        print(f"  {row.get('tool', 'N/A')}")
        print(f"    Free Plan      : {row.get('free_plan', 'N/A')}")
        print(f"    Paid Plan      : {row.get('paid_plan', 'N/A')}")
        print(f"    Starting Price : {row.get('starting_price', 'N/A')}")
        print(f"    Key Features   : {row.get('key_features', 'N/A')[:80]}...")
        print(f"    Source URL     : {row.get('source_url', 'N/A')}")
        print()


# -- HTML report generator -----------------------------------------------------

def _generate_html(data: dict, path: Path) -> None:
    actions_html = _render_actions(data.get("actions", []))
    screenshots_html = _render_screenshots(data.get("screenshots", []))
    qa_html = _render_qa(data.get("qa_findings", []))
    table_html = _render_table(data.get("final_comparison_table", []))
    dag_html = _render_dag(data.get("planner_dag", {}))
    urls_html = _render_urls(data.get("candidate_urls", []))
    browser_path_html = _render_browser_path(data.get("browser_path_chosen", {}))

    run_start = data.get("run_start", "N/A")
    run_end   = data.get("run_end",   "N/A")
    duration  = data.get("duration_seconds", "N/A")
    turns     = data.get("turn_count", 0)
    cost      = data.get("estimated_cost", "N/A")
    goal      = data.get("goal", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Browser Comparison Agent — Replay Report</title>
<style>
  :root {{
    --bg: #0f1117; --surface: #1c1f2e; --card: #252836;
    --accent: #6c63ff; --accent2: #00d4aa; --text: #e2e8f0;
    --muted: #8892a4; --border: #2d3148; --pass: #22c55e;
    --warn: #f59e0b; --fail: #ef4444;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  a {{ color: var(--accent2); text-decoration: none; }} a:hover {{ text-decoration: underline; }}
  h1 {{ font-size: 1.8rem; font-weight: 700; background: linear-gradient(90deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  h2 {{ font-size: 1.15rem; font-weight: 600; color: var(--accent2); margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  h3 {{ font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 8px; }}
  .header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 24px 40px; }}
  .goal {{ background: var(--card); border-left: 4px solid var(--accent); padding: 12px 16px; border-radius: 4px; margin-top: 12px; font-size: 0.9rem; color: var(--muted); }}
  .container {{ max-width: 1300px; margin: 0 auto; padding: 32px 40px; }}
  .section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px; margin-bottom: 28px; }}
  /* DAG */
  .dag {{ display: flex; align-items: center; flex-wrap: wrap; gap: 0; }}
  .dag-node {{ background: var(--card); border: 1.5px solid var(--border); border-radius: 8px; padding: 10px 16px; font-size: 0.8rem; text-align: center; min-width: 140px; position: relative; }}
  .dag-node.input {{ border-color: var(--accent); }}
  .dag-node.output {{ border-color: var(--accent2); }}
  .dag-node.skill {{ border-color: #8b5cf6; }}
  .dag-arrow {{ color: var(--muted); font-size: 1.2rem; padding: 0 6px; }}
  /* Actions table */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: var(--card); color: var(--accent2); font-weight: 600; padding: 10px 12px; text-align: left; border-bottom: 2px solid var(--border); }}
  td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tr:hover td {{ background: var(--card); }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.72rem; font-weight: 600; }}
  .badge.success {{ background: #166534; color: #86efac; }}
  .badge.failure {{ background: #7f1d1d; color: #fca5a5; }}
  .badge.pending {{ background: #374151; color: #9ca3af; }}
  /* QA badges */
  .qa-pass {{ color: var(--pass); }} .qa-warn {{ color: var(--warn); }} .qa-fail {{ color: var(--fail); }}
  /* Screenshots */
  .screenshots-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
  .screenshot-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
  .screenshot-card img {{ width: 100%; display: block; border-bottom: 1px solid var(--border); }}
  .screenshot-card .caption {{ padding: 8px 12px; font-size: 0.78rem; color: var(--muted); }}
  /* Comparison table */
  .comparison-table {{ overflow-x: auto; }}
  .comparison-table th {{ white-space: nowrap; }}
  .comparison-table td {{ max-width: 260px; }}
  .price-tag {{ display: inline-block; background: linear-gradient(135deg,#6c63ff22,#00d4aa22); border: 1px solid var(--accent); color: var(--accent2); padding: 3px 10px; border-radius: 999px; font-weight: 700; font-size: 0.85rem; }}
  /* Summary bar */
  .summary-bar {{ display: flex; gap: 24px; flex-wrap: wrap; }}
  .stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px 20px; text-align: center; }}
  .stat .val {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
  .stat .lbl {{ font-size: 0.75rem; color: var(--muted); margin-top: 2px; }}
  /* URL list */
  .url-list {{ list-style: none; }} .url-list li {{ padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }}
  .tool-name {{ font-weight: 600; color: var(--text); min-width: 160px; display: inline-block; }}
</style>
</head>
<body>

<div class="header">
  <h1>Browser Comparison Agent — Replay Report</h1>
  <div class="goal">{goal}</div>
</div>

<div class="container">

  <!-- Run Summary -->
  <div class="section">
    <h2>Run Summary</h2>
    <div class="summary-bar">
      <div class="stat"><div class="val">{turns}</div><div class="lbl">Browser Actions</div></div>
      <div class="stat"><div class="val">{len(data.get('screenshots',[]))}</div><div class="lbl">Screenshots</div></div>
      <div class="stat"><div class="val">{len(data.get('final_comparison_table',[]))}</div><div class="lbl">Tools Compared</div></div>
      <div class="stat"><div class="val">{duration}s</div><div class="lbl">Duration</div></div>
      <div class="stat"><div class="val">{cost}</div><div class="lbl">Estimated Cost</div></div>
      <div class="stat"><div class="val" style="font-size:0.9rem;color:var(--accent2);">See below</div><div class="lbl">Browser Path</div></div>
    </div>
    <p style="margin-top:14px;font-size:0.8rem;color:var(--muted);">
      Started: {run_start} &nbsp;|&nbsp; Ended: {run_end}
    </p>
  </div>

  <!-- Planner DAG -->
  <div class="section">
    <h2>Planner DAG</h2>
    {dag_html}
  </div>

  <!-- Candidate URLs -->
  <div class="section">
    <h2>Candidate URLs (Researcher Output)</h2>
    {urls_html}
  </div>

  <!-- Browser Path Chosen -->
  <div class="section">
    <h2>Browser Path Chosen</h2>
    {browser_path_html}
  </div>

  <!-- Browser Actions -->
  <div class="section">
    <h2>Browser Action Log ({turns} actions)</h2>
    {actions_html}
  </div>

  <!-- Screenshots -->
  <div class="section">
    <h2>Screenshots ({len(data.get('screenshots',[]))} captured)</h2>
    {screenshots_html}
  </div>

  <!-- QA Findings -->
  <div class="section">
    <h2>QA / Critic Findings</h2>
    {qa_html}
  </div>

  <!-- Final Comparison Table -->
  <div class="section">
    <h2>Final Comparison Table</h2>
    {table_html}
  </div>

</div>

<div style="text-align:center;padding:20px;color:var(--muted);font-size:0.78rem;border-top:1px solid var(--border);">
  Generated by Browser Comparison Agent &nbsp;|&nbsp;
  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
</div>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")


# -- HTML section renderers ----------------------------------------------------

def _render_dag(dag: dict) -> str:
    nodes = {n["id"]: n for n in dag.get("nodes", [])}
    edges = dag.get("edges", [])
    # Build ordered chain (linear for our pipeline)
    ordered = sorted(dag.get("nodes", []), key=lambda n: n.get("order", 0))
    parts = []
    for i, node in enumerate(ordered):
        cls = node.get("type", "skill")
        parts.append(f'<div class="dag-node {cls}"><strong>{node["label"]}</strong></div>')
        if i < len(ordered) - 1:
            # Check if there's a split (two outputs)
            next_nodes = [e["to"] for e in edges if e["from"] == node["id"]]
            if len(next_nodes) > 1:
                parts.append('<div class="dag-arrow">⇒ ⇒</div>')
            else:
                parts.append('<div class="dag-arrow">→</div>')
    return f'<div class="dag">{"".join(parts)}</div>'


def _render_browser_path(per_tool_paths: dict) -> str:
    """Render the 5-path taxonomy table showing which path each tool used."""
    all_paths = [
        ("Extract Static page",         "Rendered DOM text extraction (innerText + regex). Cheapest path — works when JS renders text into the page body."),
        ("Deterministic CSS selectors",  "Target specific CSS selectors for plan cards or price elements. Used when page structure is stable and known."),
        ("A11y Accessibility tree",      "Traverse the browser accessibility tree to find labelled price/plan nodes. Framework-agnostic."),
        ("Vision Set-of-marks",          "Screenshot the page, pass to a vision LLM with bounding-box marks. Most expensive; handles any layout."),
        ("Gateway Blocked",              "Site blocked automation or navigation failed. Agent records N/A and reports the block."),
    ]

    path_rows = []
    for path_name, description in all_paths:
        tools_using = [t for t, p in per_tool_paths.items() if p == path_name]
        if tools_using:
            badge = f'<span style="color:var(--pass);font-weight:700;">&#10003; USED</span> — {", ".join(tools_using)}'
        else:
            badge = '<span style="color:var(--muted);">not used this run</span>'
        path_rows.append(f"""<tr>
          <td><strong>{path_name}</strong></td>
          <td style="font-size:0.8rem;color:var(--muted)">{description}</td>
          <td>{badge}</td>
        </tr>""")

    return f"""<table>
      <thead><tr><th>Path</th><th>Strategy</th><th>This Run</th></tr></thead>
      <tbody>{"".join(path_rows)}</tbody>
    </table>"""


def _render_urls(urls: list) -> str:
    items = []
    for t in urls:
        items.append(
            f'<li><span class="tool-name">{t["name"]}</span>'
            f'<a href="{t["pricing_url"]}" target="_blank">{t["pricing_url"]}</a>'
            f' &nbsp;<span style="color:var(--muted);font-size:0.8rem;">— {t.get("notes","")}</span></li>'
        )
    return f'<ul class="url-list">{"".join(items)}</ul>'


def _render_actions(actions: list) -> str:
    if not actions:
        return "<p style='color:var(--muted)'>No actions recorded.</p>"

    rows = []
    for a in actions:
        result = str(a.get("result", ""))
        if "success" in result.lower():
            badge = f'<span class="badge success">success</span>'
        elif "failure" in result.lower() or "error" in result.lower():
            badge = f'<span class="badge failure">failure</span>'
        else:
            badge = f'<span class="badge pending">{result[:40]}</span>'

        rows.append(f"""<tr>
          <td>{a.get('step','')}</td>
          <td><code>{a.get('action','')}</code></td>
          <td>{a.get('target','')}</td>
          <td style="max-width:220px;word-break:break-all;font-size:0.75rem;">{a.get('page','')}</td>
          <td>{badge}</td>
          <td style="font-size:0.72rem;color:var(--muted)">{a.get('timestamp','')}</td>
        </tr>""")

    return f"""<table>
      <thead><tr><th>#</th><th>Action</th><th>Target</th><th>Page URL</th><th>Result</th><th>Timestamp (UTC)</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>"""


def _render_screenshots(screenshots: list) -> str:
    if not screenshots:
        return "<p style='color:var(--muted)'>No screenshots recorded.</p>"
    cards = []
    for sc in screenshots:
        name = sc.split("/")[-1] if "/" in sc else sc.split("\\")[-1]
        label = name.replace("_", " ").replace(".png", "")
        cards.append(
            f'<div class="screenshot-card">'
            f'<img src="{sc}" alt="{label}" onerror="this.style.display=\'none\'">'
            f'<div class="caption">{label}</div>'
            f"</div>"
        )
    return f'<div class="screenshots-grid">{"".join(cards)}</div>'


def _render_qa(findings: list) -> str:
    if not findings:
        return "<p style='color:var(--muted)'>No QA findings.</p>"
    rows = []
    for f in findings:
        status = f.get("status", "")
        cls = {"pass": "qa-pass", "warn": "qa-warn", "fail": "qa-fail"}.get(status, "")
        icon = {"pass": "✓", "warn": "⚠", "fail": "✗"}.get(status, "?")
        rows.append(f"""<tr>
          <td>{f.get('tool','')}</td>
          <td>{f.get('check','')}</td>
          <td class="{cls}">{icon} {status}</td>
          <td style="font-size:0.8rem;color:var(--muted)">{f.get('detail','')}</td>
        </tr>""")
    return f"""<table>
      <thead><tr><th>Tool</th><th>Check</th><th>Status</th><th>Detail</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>"""


def _render_table(rows: list) -> str:
    if not rows:
        return "<p style='color:var(--muted)'>No data extracted.</p>"
    headers = ["Tool", "Free Plan", "Paid Plan", "Starting Price", "Key Features", "Source URL", "Notes"]
    keys    = ["tool", "free_plan", "paid_plan", "starting_price", "key_features", "source_url", "notes"]
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for row in rows:
        cells = []
        for k in keys:
            val = row.get(k, "N/A")
            if k == "starting_price":
                val = f'<span class="price-tag">{val}</span>'
            elif k == "source_url":
                val = f'<a href="{val}" target="_blank">{val}</a>'
            elif k == "tool":
                val = f"<strong>{val}</strong>"
            cells.append(f"<td>{val}</td>")
        trs.append(f"<tr>{''.join(cells)}</tr>")
    return f"""<div class="comparison-table"><table>
      <thead><tr>{ths}</tr></thead>
      <tbody>{"".join(trs)}</tbody>
    </table></div>"""


# -- Console helpers -----------------------------------------------------------

def _banner(title: str) -> None:
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def _section(step: str, title: str) -> None:
    print(f"\n[{step}] {title}")
    print("  " + "-" * 60)


# -- Windows asyncio fix + entry -----------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Coding Tools Comparison Agent")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed (visible) mode — useful for recording demos",
    )
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main(headed=args.headed))
