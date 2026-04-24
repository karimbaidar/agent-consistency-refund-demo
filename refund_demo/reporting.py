import html
from pathlib import Path
from typing import Any, Dict, List


def write_html_report(report: Dict[str, Any], path: Path) -> None:
    receipts = report["receipts"]
    graph = report.get("causality_graph", {"nodes": [], "edges": []})
    path.write_text(_render(report, receipts, graph), encoding="utf-8")


def _render(report: Dict[str, Any], receipts: List[Dict[str, Any]], graph: Dict[str, Any]) -> str:
    status = report["status"]
    cards = "\n".join(_receipt_card(receipt) for receipt in receipts)
    edges = "\n".join(_edge_row(edge) for edge in graph.get("edges", [])) or (
        "<p class=\"muted\">No causal links recorded.</p>"
    )
    failure = report.get("failure")
    failure_html = ""
    if failure:
        failure_html = (
            "<section class=\"band failure\">"
            f"<h2>{html.escape(failure['type'])}</h2>"
            f"<p>{html.escape(failure['message'])}</p>"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(report['run_id'])} consistency report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18212f;
      --muted: #667085;
      --line: #d7dde8;
      --pass: #157347;
      --fail: #b42318;
      --soft: #f4f7fb;
      --panel: #ffffff;
      --accent: #2454a6;
    }}
    body {{
      margin: 0;
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #f8fafc;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 18px 40px;
    }}
    header {{
      display: grid;
      gap: 8px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 28px; font-weight: 700; }}
    h2 {{ font-size: 18px; margin-bottom: 12px; }}
    h3 {{ font-size: 15px; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }}
    .pill.passed {{ color: var(--pass); border-color: #a7d7ba; }}
    .pill.failed {{ color: var(--fail); border-color: #f1b8b2; }}
    .grid {{
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 18px;
      margin-top: 22px;
    }}
    .band {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .failure {{
      border-color: #f1b8b2;
      background: #fff7f6;
      color: var(--fail);
      margin-top: 18px;
    }}
    .timeline {{
      display: grid;
      gap: 12px;
    }}
    .receipt {{
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
      display: grid;
      gap: 10px;
    }}
    .receipt.failed {{ border-left-color: var(--fail); }}
    .receipt.passed {{ border-left-color: var(--pass); }}
    .receipt-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .smallgrid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .metric {{
      background: var(--soft);
      border-radius: 6px;
      padding: 8px;
    }}
    .metric strong {{
      display: block;
      font-size: 16px;
    }}
    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 0 7px;
      border-radius: 6px;
      background: var(--soft);
      color: var(--muted);
      font-size: 12px;
    }}
    .tag.pass {{ color: var(--pass); }}
    .tag.fail {{ color: var(--fail); }}
    .edge {{
      display: grid;
      gap: 4px;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      overflow-wrap: anywhere;
    }}
    .edge:last-child {{ border-bottom: 0; }}
    .muted {{ color: var(--muted); }}
    code {{
      background: var(--soft);
      padding: 2px 5px;
      border-radius: 4px;
    }}
    @media (max-width: 860px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .smallgrid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(report['run_id'])}</h1>
    <div class="meta">
      <span class="pill {html.escape(status)}">{html.escape(status.upper())}</span>
      <span class="pill">scenario: {html.escape(report.get('scenario', 'custom'))}</span>
      <span class="pill">provider: {html.escape(report.get('provider', 'unknown'))}</span>
      <span class="pill">receipts: {len(receipts)}</span>
    </div>
  </header>
  {failure_html}
  <section class="grid">
    <div class="band">
      <h2>Receipt Timeline</h2>
      <div class="timeline">{cards}</div>
    </div>
    <aside class="band">
      <h2>Causal Links</h2>
      {edges}
    </aside>
  </section>
</main>
</body>
</html>"""


def _receipt_card(receipt: Dict[str, Any]) -> str:
    status = receipt["status"]
    state_read_count = len(receipt.get("state_reads", []))
    handoffs = receipt.get("handoffs", [])
    artifacts = receipt.get("proof_artifacts", [])
    outcomes = receipt.get("outcomes", [])
    issues = receipt.get("issues", [])
    issue_text = ""
    if issues:
        issue_text = "<p class=\"muted\">" + html.escape(issues[0]["message"]) + "</p>"
    detail_tags = _detail_tags(receipt, artifacts, outcomes)
    return f"""
<article class="receipt {html.escape(status)}">
  <div class="receipt-head">
    <div>
      <h3>{html.escape(receipt['step_id'])} - {html.escape(receipt['agent'])}</h3>
      <p class="muted">{html.escape(receipt['action'])}</p>
    </div>
    <span class="pill {html.escape(status)}">{html.escape(status.upper())}</span>
  </div>
  <div class="smallgrid">
    <div class="metric">
      <span class="muted">state reads</span><strong>{state_read_count}</strong>
    </div>
    <div class="metric"><span class="muted">handoffs</span><strong>{len(handoffs)}</strong></div>
    <div class="metric"><span class="muted">artifacts</span><strong>{len(artifacts)}</strong></div>
    <div class="metric"><span class="muted">outcomes</span><strong>{len(outcomes)}</strong></div>
  </div>
  {detail_tags}
  {issue_text}
</article>"""


def _detail_tags(
    receipt: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    outcomes: List[Dict[str, Any]],
) -> str:
    tags = []
    for handoff_id in receipt.get("consumed_handoff_ids", []):
        tags.append(("handoff", handoff_id.rsplit(":", 1)[-1], ""))
    for artifact in artifacts:
        state = "verified" if artifact.get("verified") else "unverified"
        css = "pass" if artifact.get("verified") else "fail"
        tags.append(("artifact", f"{artifact['name']} {state}", css))
    for outcome in outcomes:
        state = "passed" if outcome.get("passed") else "failed"
        css = "pass" if outcome.get("passed") else "fail"
        tags.append(("outcome", f"{outcome['name']} {state}", css))
    if not tags:
        return ""
    rendered = "".join(
        f"<span class=\"tag {html.escape(css)}\">"
        f"{html.escape(prefix)}: {html.escape(value)}</span>"
        for prefix, value, css in tags
    )
    return f"<div class=\"tags\">{rendered}</div>"


def _edge_row(edge: Dict[str, Any]) -> str:
    detail = edge.get("handoff_id") or edge.get("artifact_id") or edge["kind"]
    return (
        "<div class=\"edge\">"
        f"<strong>{html.escape(edge['kind'])}</strong>"
        f"<span><code>{html.escape(edge['from'])}</code> to "
        f"<code>{html.escape(edge['to'])}</code></span>"
        f"<span class=\"muted\">{html.escape(detail)}</span>"
        "</div>"
    )
