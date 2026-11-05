"""
front_app.py - MAIN FILE of GraderGent (entry point).

Two ways to use it:

  1) Web UI (Gradio, plain and colourless):
         python front_app.py
     then open http://127.0.0.1:7860

  2) Command line (no browser, good for batch grading / scripts / CI):
         python front_app.py --cli samples/add_basic.c --rules rules/add_rules.json
         python front_app.py --cli samples/*.c            (grade several files)

This file only handles input/output (upload, buttons, printing). ALL grading
logic lives in coordinator.py and analyzers/.
"""
import argparse
import glob
import html
import json
import os
import sys
import tempfile

import coordinator
import dashboard
import rules_loader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(BASE_DIR, "rules")


# ----------------------------------------------------------------------------
# Small helpers used by both the UI and the CLI
# ----------------------------------------------------------------------------
def list_rule_files():
    """File names of all rule sets in rules/ (the instructor edits these files)."""
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(RULES_DIR, "*.json")))


def show_rules(rules_name):
    """Text of a rules file, for display in the UI."""
    try:
        with open(os.path.join(RULES_DIR, rules_name), encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        return f"Cannot read rules file: {e}"


def run_grading(c_file, rules_name):
    """
    Called by the UI button.
    Returns (text report, JSON report, [saved file paths]).
    """
    if not c_file:
        return "Please upload a .c file first.", None, None
    if not rules_name:
        return "No rules file found in rules/.", None, None
    try:
        report, text, paths = coordinator.grade_submission(
            c_file, os.path.join(RULES_DIR, rules_name))
    except rules_loader.RulesError as e:
        return f"Problem with the rules file: {e}", None, None
    except Exception as e:                                  # never show a stack trace to the user
        return f"Grading failed unexpectedly: {e!r}", None, None
    return text, report, list(paths)


def load_source_file(file_path):
    if not file_path:
        return "", "submission.c", ""
    try:
        with open(file_path, encoding="utf-8") as source_file:
            code = source_file.read()
        name = os.path.basename(file_path)
        return code, name, f"Loaded {html.escape(name)} · {len(code.splitlines())} lines"
    except (OSError, UnicodeError) as e:
        return "", "submission.c", f"Could not read source file: {html.escape(str(e))}"


def validate_rule_upload(file_path):
    if not file_path:
        return None, "<span class='upload-hint'>Drop a JSON rules file to validate and load it.</span>", ""
    try:
        rules = rules_loader.load_rules(file_path)
        name = os.path.basename(file_path)
        size = os.path.getsize(file_path)
        metrics = rules.get("metrics", [])
        metric_list = "".join(
            f"<li><span>{html.escape(str(metric['name']).replace('_', ' ').title())}</span>"
            f"<b>{float(metric['weight']) * 100:.0f}%</b></li>"
            for metric in metrics
        )
        details = (
            f"<div class='uploaded-file'><span class='file-check'>✓</span><div>"
            f"<strong>{html.escape(name)}</strong><small>{size / 1024:.1f} KB · "
            f"{len(metrics)} validated rules</small></div><span class='file-state'>Ready</span></div>"
            f"<ul class='rule-list'>{metric_list}</ul>"
        )
        return file_path, details, f"Uploaded rules: {name}"
    except (rules_loader.RulesError, OSError, ValueError) as e:
        return None, f"<div class='upload-error'>{html.escape(str(e))}</div>", ""


def render_rule_summary(rules_name):
    if not rules_name:
        return "<span class='upload-hint'>No built-in rule set is available.</span>"
    try:
        rules = rules_loader.load_rules(os.path.join(RULES_DIR, rules_name))
        metrics = rules.get("metrics", [])
        items = "".join(
            f"<li><span>{html.escape(str(metric['name']).replace('_', ' ').title())}</span>"
            f"<b>{float(metric['weight']) * 100:.0f}%</b></li>"
            for metric in metrics
        )
        return f"<div class='rule-set-title'><b>{html.escape(rules_name)}</b><span>{len(metrics)} checks</span></div><ul class='rule-list'>{items}</ul>"
    except (rules_loader.RulesError, OSError) as e:
        return f"<div class='upload-error'>{html.escape(str(e))}</div>"


def run_dashboard_analysis(source_code, source_name, rules_name, uploaded_rules, current_report, progress=None):
    if not source_code or not source_code.strip():
        return dashboard.render_dashboard(current_report), dashboard.render_table(current_report), current_report, "<span class='analysis-error'>Paste or upload a C source file to begin.</span>"
    rules_path = uploaded_rules or (os.path.join(RULES_DIR, rules_name) if rules_name else None)
    if not rules_path:
        return dashboard.render_dashboard(current_report), dashboard.render_table(current_report), current_report, "<span class='analysis-error'>Choose a rule set or upload a validated JSON rule file.</span>"
    try:
        if progress:
            progress(0.08, desc="Preparing source")
        safe_name = os.path.basename(source_name or "submission.c")
        if not safe_name.lower().endswith(".c"):
            safe_name = os.path.splitext(safe_name)[0] + ".c"
        with tempfile.TemporaryDirectory(prefix="gradergent_ui_") as workdir:
            source_path = os.path.join(workdir, safe_name)
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source_code)
            if progress:
                progress(0.2, desc="Running configured analyzers")
            report, _, _ = coordinator.grade_submission(source_path, rules_path)
        if progress:
            progress(1, desc="Analysis complete")
        return (
            dashboard.render_dashboard(report),
            dashboard.render_table(report),
            report,
            "<span class='analysis-success'>Analysis complete · results are ready</span>",
        )
    except (rules_loader.RulesError, OSError, ValueError) as e:
        message = html.escape(str(e))
        return dashboard.render_dashboard(current_report), dashboard.render_table(current_report), current_report, f"<span class='analysis-error'>{message}</span>"
    except Exception as e:
        message = html.escape(repr(e))
        return dashboard.render_dashboard(current_report), dashboard.render_table(current_report), current_report, f"<span class='analysis-error'>Analysis failed: {message}</span>"


def filter_result_table(report, search, category, status, sort, page):
    return dashboard.render_table(report or dashboard.load_preview_report(), search, category, status, sort, page)


def load_previous_report(path):
    if not path:
        return dashboard.load_preview_report()
    try:
        with open(path, encoding="utf-8") as report_file:
            return json.load(report_file)
    except (OSError, ValueError):
        return dashboard.load_preview_report()


def export_dashboard_report(report, file_type):
    if not report:
        return None, "<span class='analysis-error'>Run an analysis before exporting.</span>"
    try:
        path = dashboard.export_report(report, file_type)
        return path, f"<span class='analysis-success'>Export ready · {html.escape(os.path.basename(path))}</span>"
    except ImportError as e:
        return None, f"<span class='analysis-error'>Export dependency missing: {html.escape(str(e))}</span>"
    except Exception as e:
        return None, f"<span class='analysis-error'>Export failed: {html.escape(str(e))}</span>"


# ----------------------------------------------------------------------------
# Web UI
# ----------------------------------------------------------------------------
def build_ui():
    import gradio as gr   # imported here so that --cli works without gradio installed

    theme = gr.themes.Soft(
        primary_hue="blue", secondary_hue="purple", neutral_hue="slate"
    )
    with open(os.path.join(BASE_DIR, "dashboard.css"), encoding="utf-8") as css_file:
        css = css_file.read()
    rule_files = list_rule_files()
    preview = dashboard.load_preview_report()
    history_paths = sorted(
        glob.glob(os.path.join(BASE_DIR, "reports", "*.json"))
        + glob.glob(os.path.join(BASE_DIR, "sample_reports", "*.json")),
        key=os.path.getmtime,
        reverse=True,
    )
    history_choices = [(os.path.basename(path), path) for path in history_paths]
    initial_history = history_paths[0] if history_paths else None

    with gr.Blocks(title="GraderGent · Code Analysis", theme=theme, css=css) as demo:
        gr.HTML("<style>@media(max-width:640px){html,body,gradio-app,.gradio-container{width:100%!important;max-width:100%!important;min-width:0!important;overflow-x:hidden!important;box-sizing:border-box!important}.gradio-container{padding:0 11px 28px!important}.gradio-container>main{width:100%!important;max-width:none!important;min-width:0!important;padding:0!important}.gradio-container>main>.wrap,.gradio-container>main>.wrap>.contain{width:100%!important;max-width:100%!important;min-width:0!important}}</style>", elem_id="responsive-global-style")
        report_state = gr.State(preview)
        uploaded_rules_state = gr.State(None)
        source_name_state = gr.State("submission.c")

        with gr.Row(elem_classes="topbar"):
            gr.HTML("""<div class="brand-lockup"><span class="brand-mark"><svg viewBox="0 0 24 24"><path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/></svg></span><div><div class="brand-name">GraderGent</div><div class="brand-caption">Code analysis &amp; rule validation</div></div></div>""")
            gr.HTML("""<div class="profile-lockup"><span class="notification-mark" title="Notifications">♧</span><span class="profile-avatar">AG</span><span class="profile-copy">Analysis Group<small>Workspace</small></span></div>""")

        with gr.Tabs(elem_classes="main-nav"):
            with gr.Tab("Dashboard"):
                gr.HTML("""<div class="page-intro"><div><h1>Code analysis workspace</h1><p>Validate a C submission against your configured quality rules.</p></div><span class="intro-chip">Analysis engine ready</span></div>""")
                with gr.Row(elem_classes="workspace-row"):
                    with gr.Column(scale=1, elem_classes="workspace-card"):
                        gr.HTML("<h3>Source Code Input</h3><p class='workspace-subtitle'>Paste code or upload a C source file to start an analysis.</p>")
                        with gr.Row(elem_classes="code-toolbar"):
                            language = gr.Dropdown(
                                choices=["C", "C++", "Python", "Java", "JavaScript"],
                                value="C", label="Language", scale=1, elem_classes="compact-dropdown",
                            )
                            language_notice = gr.HTML("<span class='code-hint'>The analysis engine currently runs C rules.</span>")
                        code_input = gr.Code(
                            value="", language="c", label="", lines=20, interactive=True,
                            elem_classes="code-area",
                        )
                        with gr.Row(elem_classes="button-row"):
                            clear_code = gr.Button("Clear code", elem_classes="secondary-button", size="sm")
                            source_file = gr.File(label="Upload source", file_types=[".c"], type="filepath", scale=2, elem_classes="code-upload")
                        source_upload_status = gr.HTML("<span class='code-hint'>Accepted format: .c</span>")

                    with gr.Column(scale=1, elem_classes="workspace-card"):
                        gr.HTML("<h3>Rule Configuration</h3><p class='workspace-subtitle'>Choose a built-in set or upload a validated JSON rule file.</p>")
                        rules = gr.Dropdown(
                            choices=rule_files,
                            value=rule_files[0] if rule_files else None,
                            label="Built-in rule set", elem_classes="compact-dropdown",
                        )
                        with gr.Row(elem_classes="upload-zone"):
                            rule_file = gr.File(label="Drop a JSON rule file here", file_types=[".json"], type="filepath")
                        with gr.Row(elem_classes="button-row"):
                            upload_rules = gr.Button("Upload rules", elem_classes="secondary-button", size="sm")
                            remove_rules = gr.Button("Remove upload", elem_classes="secondary-button", size="sm")
                        rule_upload_status = gr.HTML("<span class='upload-hint'>Upload a JSON file to validate its rule definitions.</span>")
                        rule_summary = gr.HTML(render_rule_summary(rule_files[0] if rule_files else None))

                with gr.Row(elem_classes="button-row"):
                    run_button = gr.Button("Run Analysis", variant="primary", elem_classes="run-button", scale=1)
                    analysis_status = gr.HTML("<span class='code-hint'>Ready for a new analysis.</span>", elem_classes="analysis-status")
                gr.HTML("<div class='section-divider'></div>")
                result_dashboard = gr.HTML(dashboard.render_dashboard(preview))

                gr.HTML("<div class='section-divider'></div><div class='results-heading'><div><div class='eyebrow'>RULE VALIDATION</div><h2>Detailed results</h2><p>Search, filter, and inspect evidence for each configured metric.</p></div></div>")
                with gr.Row(elem_classes="filter-row"):
                    search_filter = gr.Textbox(label="Search", placeholder="Rule, analyzer, or feedback", scale=2)
                    category_filter = gr.Dropdown(
                        choices=["All categories", "Correctness", "Code quality", "Performance", "Safety", "Review", "Other"],
                        value="All categories", label="Category", scale=1,
                    )
                    status_filter = gr.Dropdown(
                        choices=["All statuses", "PASS", "FAIL", "WARNING"],
                        value="All statuses", label="Status", scale=1,
                    )
                    sort_filter = gr.Dropdown(
                        choices=["Score: low to high", "Score: high to low", "Name: A to Z"],
                        value="Score: low to high", label="Sort", scale=1,
                    )
                    page_filter = gr.Number(value=1, minimum=1, maximum=100, step=1, precision=0, label="Page", scale=0)
                    filter_button = gr.Button("Apply filters", elem_classes="secondary-button filter-button", scale=0)
                result_table = gr.HTML(dashboard.render_table(preview))

                with gr.Row(elem_classes="reset-row"):
                    reset_button = gr.Button("Reset analysis", elem_classes="secondary-button")
                    with gr.Row(elem_classes="export-row"):
                        export_pdf = gr.Button("Export PDF", elem_classes="secondary-button", size="sm")
                        export_excel = gr.Button("Export Excel", elem_classes="secondary-button", size="sm")
                with gr.Row():
                    pdf_download = gr.File(label="PDF report", interactive=False)
                    excel_download = gr.File(label="Excel report", interactive=False)
                    export_status = gr.HTML(elem_classes="export-status")

            with gr.Tab("Analysis History"):
                with gr.Column(elem_classes="history-panel"):
                    gr.HTML("<h2>Analysis history</h2><p>Open a previous saved analysis or preview a bundled sample run.</p>")
                    history_picker = gr.Dropdown(choices=history_choices, value=initial_history, label="Saved analysis")
                    history_load = gr.Button("Load selected analysis", elem_classes="secondary-button")
                    history_dashboard = gr.HTML(dashboard.render_dashboard(preview))
                    history_table = gr.HTML(dashboard.render_table(preview))

            with gr.Tab("Reports"):
                with gr.Column(elem_classes="history-panel"):
                    gr.HTML("<h2>Reports</h2><p>Analysis reports are saved as JSON and student-readable text in the reports directory.</p>")
                    saved_reports = sorted(glob.glob(os.path.join(BASE_DIR, "reports", "*.json")) + glob.glob(os.path.join(BASE_DIR, "reports", "*.txt")))
                    if saved_reports:
                        gr.File(value=saved_reports, label="Saved report files", file_count="multiple", interactive=False)
                    else:
                        gr.HTML("<div class='upload-hint'>Run an analysis to create your first report.</div>")
                    report_preview = gr.JSON(value=preview, label="Sample report data")

            with gr.Tab("Settings"):
                with gr.Column(elem_classes="history-panel"):
                    gr.HTML("<h2>Workspace settings</h2><p>Current capabilities and analysis environment.</p><ul class='settings-list'><li><span>Analysis language</span><b>C (gcc, C11)</b></li><li><span>Rule format</span><b>Validated JSON</b></li><li><span>Report formats</span><b>JSON · TXT · PDF · XLSX</b></li><li><span>External review</span><b>Optional local Ollama</b></li><li><span>Execution safety</span><b>Sandboxed with time and memory limits</b></li></ul>")

        def analyze_click(code, source_name, selected_language, rules_name, custom_rules, current_report, progress=gr.Progress(track_tqdm=False)):
            if selected_language != "C":
                return dashboard.render_dashboard(current_report), dashboard.render_table(current_report), current_report, "<span class='analysis-error'>The current grading engine supports C only. Choose C to run analysis.</span>"
            return run_dashboard_analysis(code, source_name, rules_name, custom_rules, current_report, progress)

        def select_language(value):
            language_map = {"C": "c", "C++": "c++", "Python": "python", "Java": "java", "JavaScript": "javascript"}
            return gr.update(language=language_map.get(value, "c")), (
                "<span class='code-hint'>The analysis engine currently runs C rules.</span>"
                if value == "C" else
                f"<span class='analysis-error'>{html.escape(value)} syntax is available; grading is currently C-only.</span>"
            )

        def select_builtin_rules(rules_name):
            return None, None, render_rule_summary(rules_name), "<span class='upload-hint'>Using the selected built-in rules.</span>"

        def clear_uploaded_rules(rules_name):
            return None, None, render_rule_summary(rules_name), "<span class='upload-hint'>Uploaded rules removed.</span>"

        def clear_analysis():
            sample = dashboard.load_preview_report()
            return (
                "", "submission.c", None, None,
                "<span class='upload-hint'>Upload a JSON file to validate its rule definitions.</span>",
                dashboard.render_dashboard(sample), dashboard.render_table(sample), sample,
                "<span class='code-hint'>Analysis reset. Ready for a new run.</span>", None, None,
            )

        def show_history(path):
            previous = load_previous_report(path)
            return dashboard.render_dashboard(previous), dashboard.render_table(previous), previous

        def export_pdf_click(report):
            return export_dashboard_report(report, "pdf")

        def export_excel_click(report):
            return export_dashboard_report(report, "xlsx")

        source_file.change(load_source_file, inputs=source_file, outputs=[code_input, source_name_state, source_upload_status])
        clear_code.click(lambda: ("", "submission.c", "<span class='code-hint'>Editor cleared.</span>"), outputs=[code_input, source_name_state, source_upload_status])
        language.change(select_language, inputs=language, outputs=[code_input, language_notice])
        rules.change(select_builtin_rules, inputs=rules, outputs=[uploaded_rules_state, rule_file, rule_summary, rule_upload_status])
        rule_file.change(validate_rule_upload, inputs=rule_file, outputs=[uploaded_rules_state, rule_summary, rule_upload_status])
        upload_rules.click(validate_rule_upload, inputs=rule_file, outputs=[uploaded_rules_state, rule_summary, rule_upload_status])
        remove_rules.click(clear_uploaded_rules, inputs=rules, outputs=[uploaded_rules_state, rule_file, rule_summary, rule_upload_status])
        run_button.click(
            analyze_click,
            inputs=[code_input, source_name_state, language, rules, uploaded_rules_state, report_state],
            outputs=[result_dashboard, result_table, report_state, analysis_status],
        )
        filter_button.click(
            filter_result_table,
            inputs=[report_state, search_filter, category_filter, status_filter, sort_filter, page_filter],
            outputs=result_table,
        )
        reset_button.click(
            clear_analysis,
            outputs=[code_input, source_name_state, rule_file, uploaded_rules_state, rule_upload_status,
                     result_dashboard, result_table, report_state, analysis_status, pdf_download, excel_download],
        )
        history_load.click(show_history, inputs=history_picker, outputs=[history_dashboard, history_table, report_preview])
        export_pdf.click(export_pdf_click, inputs=report_state, outputs=[pdf_download, export_status])
        export_excel.click(export_excel_click, inputs=report_state, outputs=[excel_download, export_status])
    return demo


# ----------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------
def run_cli(files, rules_path):
    """Grade each file, print the text report, return a process exit code."""
    status = 0
    for path in files:
        try:
            _, text, paths = coordinator.grade_submission(path, rules_path)
        except (rules_loader.RulesError, OSError) as e:
            print(f"{path}: {e}", file=sys.stderr)
            status = 1
            continue
        print(text)
        print(f"[saved: {paths[0]} , {paths[1]}]\n")
    return status


def main():
    parser = argparse.ArgumentParser(description="GraderGent - rule-driven C grader")
    parser.add_argument("--cli", nargs="+", metavar="FILE.c",
                        help="grade these files on the command line instead of starting the UI")
    parser.add_argument("--rules", default=os.path.join(RULES_DIR, "add_rules.json"),
                        help="rules file for --cli (default: rules/add_rules.json)")
    parser.add_argument("--host", default="127.0.0.1", help="UI host (use 0.0.0.0 to share on a LAN)")
    parser.add_argument("--port", type=int, default=7860, help="UI port")
    args = parser.parse_args()

    if args.cli:
        sys.exit(run_cli(args.cli, args.rules))
    build_ui().launch(server_name=args.host, server_port=args.port)


if __name__ == "__main__":
    main()
