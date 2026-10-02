"""One self-contained HTML report. No remote scripts and no CDN."""

from html import escape

from agentshield.report.schema import ReportBody, ScenarioOutcome


def render_html(report: ReportBody) -> str:
    """Write the suite table, the failing rules, and trace excerpts for failures."""
    rows = "\n".join(_scenario_row(item) for item in report.scenarios)
    failures = "\n".join(_failure_block(item) for item in report.scenarios if not item.passed)
    if not failures:
        failures = "<p>No failing rules.</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Agentshield report {escape(report.agent_id)}</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
.pass {{ background: #e7f6e7; }}
.fail {{ background: #fde8e8; }}
pre {{ white-space: pre-wrap; background: #f6f6f6; padding: 0.8rem; }}
</style>
</head>
<body>
<h1>Agentshield report</h1>
<p>Agent {escape(report.agent_id)}. Policy version {report.policy_version}.
Pack {escape(report.scenario_pack_hash)}. Created {escape(report.created_at)}.</p>
<h2>Scenarios</h2>
<table>
<thead><tr><th>Suite</th><th>Scenario</th><th>Outcome</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<h2>Failing rules</h2>
{failures}
</body>
</html>
"""


def _scenario_row(scenario: ScenarioOutcome) -> str:
    outcome = "Pass" if scenario.passed else "Fail"
    css = "pass" if scenario.passed else "fail"
    return (
        f'<tr class="{css}"><td>{escape(scenario.suite)}</td>'
        f"<td>{escape(scenario.id)}</td><td>{outcome}</td></tr>"
    )


def _failure_block(scenario: ScenarioOutcome) -> str:
    rules = scenario.failing_rules or []
    if rules:
        items = "\n".join(
            "<li><code>"
            + escape(rule.id)
            + "</code> ("
            + escape(rule.severity)
            + "): "
            + escape(rule.reason)
            + "</li>"
            for rule in rules
        )
    else:
        items = f"<li>{escape(scenario.reason)}</li>"
    excerpt = escape(scenario.excerpt) if scenario.excerpt else "No excerpt."
    return f"<section><h3>{escape(scenario.id)}</h3><ul>{items}</ul><pre>{excerpt}</pre></section>"
