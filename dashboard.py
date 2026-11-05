"""HTML rendering and exports for the GraderGent analytics dashboard."""
import glob
import html
import json
import math
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
SAMPLE_REPORT_DIR = os.path.join(BASE_DIR, "sample_reports")

CATEGORY_BY_METRIC = {
    "correctness": "Correctness",
    "logical": "Correctness",
    "syntax": "Code quality",
    "structure": "Code quality",
    "modularity": "Code quality",
    "complexity": "Performance",
    "memory_safety": "Safety",
    "readability": "Review",
    "originality": "Review",
}
CATEGORY_COLORS = {
    "Correctness": "#2563eb",
    "Code quality": "#7c3aed",
    "Performance": "#0891b2",
    "Safety": "#10b981",
    "Review": "#f59e0b",
}


def load_preview_report():
    """Use the supplied grading example for the initial UI render."""
    return {
        "submission": "sample.c",
        "problem": "add_two_integers",
        "grade": 79.0,
        "partial": False,
        "metrics": [
            {
                "name": "correctness",
                "analyzer": "io_tests",
                "score": 0.9,
                "weight": 0.2,
                "contribution": 18.0,
                "feedback": "8 of 10 tests pass.",
                "suggestions": ["Fix the failing hidden tests listed in the detailed report."],
                "evidence": {"tests_passed": 8, "tests_total": 10, "failing": [7, 8]},
            },
            {
                "name": "syntax",
                "analyzer": "compiler_warnings",
                "score": 0.9,
                "weight": 0.1,
                "contribution": 9.0,
                "feedback": "One -Wunused-parameter warning remains.",
                "suggestions": ["Remove the unused parameter warning in the function signature."],
                "evidence": {"warning_count": 1, "warnings": ["-Wunused-parameter"]},
            },
            {
                "name": "structure",
                "analyzer": "static_analysis",
                "score": 0.6,
                "weight": 0.1,
                "contribution": 6.0,
                "feedback": "No headers and a single-block implementation reduce structure quality.",
                "suggestions": ["Split logic into helper functions and add a header."],
                "evidence": {"headers": 0, "single_block": True},
            },
            {
                "name": "modularity",
                "analyzer": "function_split",
                "score": 0.3,
                "weight": 0.1,
                "contribution": 3.0,
                "feedback": "Only main() exists; no helper functions are defined.",
                "suggestions": ["Extract repeated logic into a helper function and call it from main."],
                "evidence": {"functions_defined": 1, "helpers_used": 0},
            },
            {
                "name": "logical",
                "analyzer": "edge_case_runner",
                "score": 0.8,
                "weight": 0.1,
                "contribution": 8.0,
                "feedback": "Overflow on INT_MAX + 1 is not handled.",
                "suggestions": ["Add a checked overflow path for signed integer limits."],
                "evidence": {"cases_passed": 8, "cases_total": 10, "failing": ["INT_MAX + 1"]},
            },
            {
                "name": "complexity",
                "analyzer": "complexity_estimator",
                "score": 1.0,
                "weight": 0.1,
                "contribution": 10.0,
                "feedback": "Estimated O(1); required O(1).",
                "suggestions": [],
                "evidence": {"required": "O(1)", "estimated": "O(1)"},
            },
            {
                "name": "memory_safety",
                "analyzer": "sanitizer_run",
                "score": 1.0,
                "weight": 0.1,
                "contribution": 10.0,
                "feedback": "No sanitizer diagnostics were reported.",
                "suggestions": [],
                "evidence": {"issues": 0},
            },
            {
                "name": "readability",
                "analyzer": "llm_review",
                "score": 0.5,
                "weight": 0.1,
                "contribution": 5.0,
                "feedback": "Code reads as cramped and terse with weak naming and minimal comments.",
                "suggestions": ["Use clearer variable names and add a few explanatory comments."],
                "evidence": {"method": "Groq / Llama 3.3 70B", "score_out_of_10": 5},
            },
            {
                "name": "originality",
                "analyzer": "similarity_flag",
                "score": 1.0,
                "weight": 0.1,
                "contribution": 10.0,
                "feedback": "Max similarity is 0.42 and it is not flagged.",
                "suggestions": [],
                "evidence": {"max_similarity": 0.42, "flagged": False},
            },
        ],
        "failures": [
            "INT_MAX + 1 overflow not handled",
            "Some hidden-tests still fail"
        ],
        "flags": [],
        "first_pass": {"compiled": True, "smoke_ok": True},
    }


def _status(metric):
    score = float(metric.get("score", 0))
    if score >= 0.999:
        return "PASS"
    if score < 0.5:
        return "FAIL"
    return "WARNING"


def _category(metric):
    return CATEGORY_BY_METRIC.get(metric.get("name"), "Other")


def _escape(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _icon(name):
    paths = {
        "score": '<path d="M12 3v3m0 12v3M3 12h3m12 0h3"/><circle cx="12" cy="12" r="8"/><path d="m9 12 2 2 4-4"/>',
        "rules": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
        "pass": '<path d="m5 12 4 4L19 6"/>',
        "fail": '<path d="m6 6 12 12M18 6 6 18"/>',
        "warning": '<path d="M12 9v4m0 4h.01"/><path d="m10.3 3.9-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3l-8-14a2 2 0 0 0-3.4 0Z"/>',
        "critical": '<path d="M12 8v4m0 4h.01"/><circle cx="12" cy="12" r="10"/>',
        "compliance": '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
        "quality": '<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z"/>',
    }
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{paths.get(name, paths["rules"])}</svg>'


def _metric_counts(report):
    metrics = report.get("metrics", [])
    statuses = [_status(metric) for metric in metrics]
    return {
        "total": len(metrics),
        "passed": statuses.count("PASS"),
        "failed": statuses.count("FAIL"),
        "warnings": statuses.count("WARNING"),
        "critical": sum(1 for metric in metrics if float(metric.get("score", 0)) < 0.5),
    }


def _weighted_contribution(metric):
    if "contribution" in metric:
        return float(metric.get("contribution", 0.0))
    weight = float(metric.get("weight", 0.0))
    score = float(metric.get("score", 0.0))
    return weight * 100.0 * score


def _weighted_total(report, metrics=None):
    items = metrics if metrics is not None else report.get("metrics", [])
    return sum(float(metric.get("weight", 0.0)) * 100.0 for metric in items)


def _score_color(score):
    if score >= 90:
        return "#10b981", "Excellent"
    if score >= 75:
        return "#2563eb", "Good"
    if score >= 50:
        return "#f59e0b", "Moderate"
    return "#ef4444", "Critical"


def _gauge(score):
    color, label = _score_color(score)
    radius = 52
    circumference = 2 * math.pi * radius
    progress = circumference * max(0, min(100, score)) / 100
    return f'''<div class="score-gauge" title="Overall score: {score:.1f} out of 100">
      <svg viewBox="0 0 128 128" role="img" aria-label="Score {score:.1f} out of 100">
        <circle class="gauge-track" cx="64" cy="64" r="{radius}" />
        <circle class="gauge-value" cx="64" cy="64" r="{radius}"
          stroke="{color}" stroke-dasharray="{progress:.2f} {circumference:.2f}"
          style="--gauge-color:{color}" />
      </svg>
      <div class="gauge-center"><strong>{score:.0f}</strong><span>/ 100</span></div>
      <div class="gauge-status" style="color:{color}"><i></i>{label}</div>
    </div>'''


def _metric_card(title, value, note, icon, tone, tooltip):
    return f'''<article class="metric-card tone-{tone}" title="{_escape(tooltip)}">
      <div class="metric-card-top"><span class="metric-icon">{_icon(icon)}</span><span class="metric-note">{_escape(note)}</span></div>
      <strong>{_escape(value)}</strong><span class="metric-title">{_escape(title)}</span>
    </article>'''


def _donut(counts):
    total = max(1, counts["total"])
    radius = 47
    circumference = 2 * math.pi * radius
    colors = {"passed": "#10b981", "failed": "#ef4444", "warnings": "#f59e0b"}
    cursor = 0
    parts = []
    for key in ("passed", "failed", "warnings"):
        length = circumference * counts[key] / total
        parts.append(
            f'<circle cx="64" cy="64" r="{radius}" fill="none" stroke="{colors[key]}" '
            f'stroke-width="15" stroke-dasharray="{length:.2f} {circumference:.2f}" '
            f'stroke-dashoffset="{-cursor:.2f}" />'
        )
        cursor += length
    return f'''<div class="donut-wrap"><svg viewBox="0 0 128 128" role="img" aria-label="Rule outcomes">
      <g transform="rotate(-90 64 64)"><circle cx="64" cy="64" r="{radius}" fill="none" stroke="#e9eef5" stroke-width="15"/>{''.join(parts)}</g>
      <text x="64" y="60" text-anchor="middle" class="donut-total">{counts['total']}</text>
      <text x="64" y="77" text-anchor="middle" class="donut-caption">checks</text>
      </svg></div>'''


def _category_bars(report):
    grouped = {}
    for metric in report.get("metrics", []):
        category = _category(metric)
        grouped.setdefault(category, []).append(float(metric.get("score", 0)) * 100)
    if not grouped:
        return '<p class="empty-state">Run an analysis to see category scores.</p>'
    rows = []
    for category, values in grouped.items():
        score = sum(values) / len(values)
        color = CATEGORY_COLORS.get(category, "#64748b")
        rows.append(f'''<div class="category-row" title="{_escape(category)} score: {score:.1f}%">
          <div class="category-label"><span>{_escape(category)}</span><b>{score:.0f}</b></div>
          <div class="bar-track"><span style="width:{max(0, min(100, score)):.1f}%;background:{color}"></span></div>
        </div>''')
    return "".join(rows)


def _performance_bars(report):
    metrics = report.get("metrics", [])
    if not metrics:
        return '<p class="empty-state">No metric results yet.</p>'
    rows = []
    for metric in metrics:
        score = max(0, min(100, float(metric.get("score", 0)) * 100))
        weight = float(metric.get("weight", 0.0))
        earned = float(metric.get("contribution", 100.0 * weight * float(metric.get("score", 0))))
        out_of = 100.0 * weight
        earned_text = f"{earned:.0f}" if earned.is_integer() else f"{earned:.1f}"
        out_of_text = f"{out_of:.0f}" if out_of.is_integer() else f"{out_of:.1f}"
        category = _category(metric)
        color = CATEGORY_COLORS.get(category, "#64748b")
        status = _status(metric)

        if status == "PASS":
            passed = score
            failed = 0
            partial = max(0, 100 - score)
        elif status == "FAIL":
            passed = 0
            failed = 100 - score
            partial = 0
        else:
            passed = 0
            failed = 0
            partial = score

        rows.append(f'''<div class="performance-row" title="{_escape(metric.get('feedback', ''))}">
          <span>{_escape(metric.get('name', 'Metric').replace('_', ' ').title())}</span>
          <div class="stacked-track"><i style="width:{passed:.1f}%;background:{color}"></i><i style="width:{failed:.1f}%;background:#ef4444"></i><i style="width:{partial:.1f}%;background:{color}"></i><i style="width:{max(0, 100-passed-failed-partial):.1f}%;background:#dce5ef"></i></div>
          <b>{earned_text}/{out_of_text}</b></div>''')
    return "".join(rows)


def _trend(report):
    sample_paths = sorted(glob.glob(os.path.join(SAMPLE_REPORT_DIR, "*.json")))
    points = []
    for path in sample_paths:
        try:
            with open(path, encoding="utf-8") as source:
                sample = json.load(source)
            if isinstance(sample.get("grade"), (int, float)):
                points.append((os.path.splitext(os.path.basename(path))[0].replace("add_", "").title(), float(sample["grade"])))
        except (OSError, ValueError):
            continue
    latest_name = os.path.splitext(os.path.basename(report.get("submission", "Current")))[0].title()
    if points and points[-1][0].lower() == latest_name.lower():
        points[-1] = ("Current", float(report.get("grade", 0)))
    else:
        points.append(("Current", float(report.get("grade", 0))))
    points = points[-6:]
    width, height, pad = 520, 160, 24
    min_value = min(0, min((value for _, value in points), default=0))
    span = max(100 - min_value, 1)
    coords = []
    for index, (_, value) in enumerate(points):
        x = pad + index * (width - 2 * pad) / max(1, len(points) - 1)
        y = height - pad - (value - min_value) / span * (height - 2 * pad)
        coords.append((x, y, value))
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in coords)
    circles = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5"><title>{_escape(points[i][0])}: {value:.1f}</title></circle>' for i, (x, y, value) in enumerate(coords))
    labels = "".join(f'<text x="{x:.1f}" y="{height - 3}" text-anchor="middle">{_escape(points[i][0][:9])}</text>' for i, (x, _, _) in enumerate(coords))
    delta = report.get("grade", 0) - points[-2][1] if len(points) > 1 else 0
    trend_label = "First recorded run" if len(points) < 2 else f"{'+' if delta >= 0 else ''}{delta:.1f} pts vs previous sample"
    return f'''<div class="trend-summary">{_escape(trend_label)}</div>
      <svg class="trend-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Analysis score trend">
        <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" />
        <polyline points="{polyline}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        <g fill="#2563eb">{circles}</g><g class="trend-labels">{labels}</g>
      </svg>'''


def render_dashboard(report):
    score = float(report.get("grade", 0))
    counts = _metric_counts(report)
    compliance = 100 * counts["passed"] / counts["total"] if counts["total"] else 0
    quality_metrics = [m for m in report.get("metrics", []) if _category(m) == "Code quality"]
    total_quality_weight = _weighted_total(report, quality_metrics)
    quality_score = 100.0 * sum(_weighted_contribution(m) for m in quality_metrics) / total_quality_weight if total_quality_weight else 0
    cards = [
        _metric_card("Total rules checked", counts["total"], "Configured metrics", "rules", "blue", "Number of configured analyzers in this run"),
        _metric_card("Rules passed", counts["passed"], "Full score", "pass", "green", "Metrics that received a full score"),
        _metric_card("Rules failed", counts["failed"], "Below 50%", "fail", "red", "Metrics scoring below 50 percent"),
        _metric_card("Warnings detected", counts["warnings"], "Needs review", "warning", "amber", "Metrics with a partial score"),
        _metric_card("Critical issues", counts["critical"], "High priority", "critical", "rose", "Metrics scoring below 50 percent"),
        _metric_card("Compliance", f"{compliance:.0f}%", "Fully passed", "compliance", "teal", "Share of metrics with a full score"),
        _metric_card("Code quality", f"{quality_score:.0f}", "Out of 100", "quality", "purple", "Average syntax, structure, and modularity score"),
    ]
    problem = _escape(report.get("problem", "C analysis"))
    partial = '<span class="partial-pill">Partial report</span>' if report.get("partial") else '<span class="live-pill"><i></i>Analysis complete</span>'
    return f'''<section class="results-dashboard">
      <div class="results-heading"><div><div class="eyebrow">ANALYSIS OVERVIEW</div><h2>Results at a glance</h2><p>{problem} <span class="heading-dot">·</span> {_escape(report.get('submission', 'submission.c'))}</p></div>{partial}</div>
      <div class="overview-grid"><article class="score-panel"><div><div class="score-kicker">OVERALL SCORE</div><p class="score-context">Weighted across all configured metrics</p></div>{_gauge(score)}</article><div class="metric-grid">{''.join(cards)}</div></div>
      <div class="analytics-grid">
        <article class="analytics-panel compliance-panel"><div class="panel-heading"><div><h3>Rule compliance</h3><p>Outcome distribution across checks</p></div><span class="panel-menu">···</span></div><div class="donut-content">{_donut(counts)}<div class="legend-list"><div><i class="legend-dot pass-dot"></i><span>Passed</span><b>{counts['passed']}</b></div><div><i class="legend-dot fail-dot"></i><span>Failed</span><b>{counts['failed']}</b></div><div><i class="legend-dot warn-dot"></i><span>Warning</span><b>{counts['warnings']}</b></div></div></div></article>
        <article class="analytics-panel"><div class="panel-heading"><div><h3>Metric breakdown</h3><p>Score coverage by configured metric</p></div><span class="panel-menu">···</span></div><div class="performance-chart">{_performance_bars(report)}</div><div class="chart-legend"><span><i class="legend-dot pass-dot"></i>Full score</span><span><i class="legend-dot fail-dot"></i>Failed</span><span><i class="legend-dot neutral-dot"></i>Partial</span></div></article>
        <article class="analytics-panel"><div class="panel-heading"><div><h3>Analysis trend</h3><p>Bundled sample reports and current run</p></div><span class="panel-menu">···</span></div>{_trend(report)}</article>
      </div>
    </section>'''


def render_table(report, search="", category="All categories", status="All statuses", sort="Score: low to high", page=1):
    metrics = report.get("metrics", [])
    rows = []
    query = (search or "").strip().lower()
    for index, metric in enumerate(metrics, 1):
        category_name = _category(metric)
        row_status = _status(metric)
        name = str(metric.get("name", "Metric"))
        analyzer = str(metric.get("analyzer", ""))
        description = str(metric.get("feedback", "No description provided."))
        haystack = " ".join((name, analyzer, category_name, description)).lower()
        if query and query not in haystack:
            continue
        if category != "All categories" and category_name != category:
            continue
        if status != "All statuses" and row_status != status:
            continue
        rows.append((index, metric, category_name, row_status, name, analyzer, description))
    if sort == "Score: high to low":
        rows.sort(key=lambda row: float(row[1].get("score", 0)), reverse=True)
    elif sort == "Name: A to Z":
        rows.sort(key=lambda row: row[4].lower())
    else:
        rows.sort(key=lambda row: float(row[1].get("score", 0)))
    page_size = 8
    pages = max(1, math.ceil(len(rows) / page_size))
    page = max(1, min(pages, int(page or 1)))
    visible = rows[(page - 1) * page_size:page * page_size]
    if not visible:
        table_rows = '<tr><td colspan="8" class="table-empty">No rule checks match these filters.</td></tr>'
    else:
        rendered = []
        for index, metric, category_name, row_status, name, analyzer, description in visible:
            score = 100 * float(metric.get("score", 0))
            weight = float(metric.get("weight", 0.0))
            contribution = float(metric.get("contribution", weight * score / 100.0 if weight else 0.0))
            weight_pct = weight * 100
            severity = "Critical" if score < 50 else "Major" if score < 100 else "Info"
            status_class = row_status.lower()
            evidence = html.escape(json.dumps(metric.get("evidence", {}), indent=2, ensure_ascii=False))
            suggestions = metric.get("suggestions", [])
            extra = "<br>".join(_escape(item) for item in suggestions) or "No additional suggestions."
            rendered.append(f'''<tr><td class="rule-id">R{index:02d}</td><td><strong>{_escape(name.replace('_', ' ').title())}</strong><small>{_escape(analyzer)}</small><div class="rule-meta">{weight_pct:.0f}% of total · {contribution:.1f}/{weight_pct:.0f} pts</div></td><td>{_escape(category_name)}</td><td class="description-cell">{_escape(description)}</td><td><span class="status-badge status-{status_class}">{row_status}</span></td><td class="score-cell">{score:.0f}</td><td><span class="severity severity-{severity.lower()}">{severity}</span></td><td><details class="row-details"><summary>Details</summary><div class="details-content"><b>Feedback</b><p>{_escape(description)}</p><b>Weight split</b><p>{weight_pct:.0f}% of total score · {contribution:.1f} weighted points</p><b>Suggestions</b><p>{extra}</p><b>Evidence</b><pre>{evidence}</pre></div></details></td></tr>''')
        table_rows = "".join(rendered)
    return f'''<div class="table-meta"><span>{len(rows)} checks</span><span>Page {page} of {pages}</span></div>
      <div class="results-table-wrap"><table class="results-table"><thead><tr><th>Rule ID</th><th>Rule name</th><th>Category</th><th>Description</th><th>Status</th><th>Score</th><th>Severity</th><th>Action</th></tr></thead><tbody>{table_rows}</tbody></table></div>'''


def export_report(report, file_type):
    """Write a PDF or XLSX report and return its path."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(report.get("submission", "analysis")))[0]
    if file_type == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        path = os.path.join(REPORT_DIR, f"{stem}_analysis.xlsx")
        workbook = Workbook()
        summary = workbook.active
        summary.title = "Summary"
        summary.append(["GraderGent analysis report"])
        summary.append(["Submission", report.get("submission", "")])
        summary.append(["Problem", report.get("problem", "")])
        summary.append(["Overall score", report.get("grade", 0)])
        summary.append(["Partial report", report.get("partial", False)])
        summary.append(["Rules checked", len(report.get("metrics", []))])
        summary.append(["Flags", " | ".join(report.get("flags", []))])
        sheet = workbook.create_sheet("Metric results")
        sheet.append(["ID", "Rule name", "Analyzer", "Category", "Status", "Score", "Weight", "Feedback", "Suggestions"])
        for index, metric in enumerate(report.get("metrics", []), 1):
            sheet.append([f"R{index:02d}", metric.get("name"), metric.get("analyzer"), _category(metric), _status(metric), round(float(metric.get("score", 0)) * 100, 1), metric.get("weight", 0), metric.get("feedback", ""), " | ".join(metric.get("suggestions", []))])
        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for cell in worksheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="17385F")
            for column in worksheet.columns:
                width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 52)
                worksheet.column_dimensions[column[0].column_letter].width = width
            for row in worksheet.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
        workbook.save(path)
        return path

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    path = os.path.join(REPORT_DIR, f"{stem}_analysis.pdf")
    document = SimpleDocTemplate(path, pagesize=landscape(letter), rightMargin=0.45 * inch, leftMargin=0.45 * inch, topMargin=0.45 * inch, bottomMargin=0.45 * inch)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=7.5, leading=9))
    content = [Paragraph("GraderGent Analysis Report", styles["Title"]), Spacer(1, 8)]
    content.append(Paragraph(f"Submission: {_escape(report.get('submission', ''))} &nbsp; | &nbsp; Problem: {_escape(report.get('problem', ''))} &nbsp; | &nbsp; Score: {float(report.get('grade', 0)):.1f}/100", styles["BodyText"]))
    content.append(Spacer(1, 14))
    data = [["Rule", "Category", "Status", "Score", "Feedback"]]
    for metric in report.get("metrics", []):
        data.append([metric.get("name", ""), _category(metric), _status(metric), f"{100 * float(metric.get('score', 0)):.0f}", Paragraph(_escape(metric.get("feedback", "")), styles["SmallCell"])])
    table = Table(data, colWidths=[1.35 * inch, 1.2 * inch, 0.8 * inch, 0.55 * inch, 6.0 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17385f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2ec")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    content.append(table)
    if report.get("flags"):
        content.extend([Spacer(1, 12), Paragraph("Flags", styles["Heading2"])])
        content.extend(Paragraph(f"• {_escape(flag)}", styles["BodyText"]) for flag in report["flags"])
    document.build(content)
    return path
