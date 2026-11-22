"""Build the README PDF that opens on a right-click of the title (v108.145).

    py tools\\build_readme_pdf.py            update the Markdown, then print the PDF
    py tools\\build_readme_pdf.py --md-only  update the Markdown only

The source is spnav_mapper/resources/SpaceNavigator_Mapper_README.md. This
script first rewrites two parts of it from the code:

* the **Version:** line, from spnav_mapper/version.py;
* section 8, the function reference: every top-level function and class
  method of the package with its source line and the first line of its
  docstring.

It then converts the Markdown to HTML with pandoc and prints it to
SpaceNavigator_Mapper_README.pdf, beside the Markdown, with Chrome or Edge
(headless). The page header, footer and page numbers come from the CSS @page
rules below. Needs pandoc (https://pandoc.org) and Chrome or Edge.
"""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "spnav_mapper"
RESOURCES = PACKAGE / "resources"
MARKDOWN = RESOURCES / "SpaceNavigator_Mapper_README.md"
PDF = RESOURCES / "SpaceNavigator_Mapper_README.pdf"

BEGIN = "<!-- BEGIN FUNCTION REFERENCE: written by tools/build_readme_pdf.py -->"
END = "<!-- END FUNCTION REFERENCE -->"

# Section 8's subsections: (title, modules), in order. A module that is in
# none of them goes to "Other modules".
GROUPS = (
    (
        "Start-up, paths and preferences",
        (
            "app.py",
            "bootstrap.py",
            "paths.py",
            "settings.py",
            "restart.py",
            "single_instance.py",
            "display_preferences.py",
            "backups.py",
        ),
    ),
    ("Windows, keyboard and device", ("win32.py", "keyboard_io.py", "devices.py")),
    ("Macros and Auto-Profiles rules", ("macros.py", "auto_profiles.py")),
    (
        "Main window, profiles and targets",
        (
            "ui/main_window.py",
            "ui/profiles.py",
            "profile_note.py",
            "ui/profile_note_dialog.py",
            "ui/targets.py",
            "ui/auto_profiles_menu.py",
            "ui/window_chrome.py",
            "ui/menu_autoclose.py",
            "ui/readme_viewer.py",
        ),
    ),
    (
        "Axis panels, key picker and macro editor",
        ("ui/axis_panel.py", "ui/keyboard_popup.py", "ui/macro_editor.py", "ui/widgets.py"),
    ),
    (
        "Display sizing and window placement",
        (
            "ui/scaling.py",
            "ui/monitor_scale.py",
            "ui/system_font.py",
            "ui/editor_fit.py",
            "ui/placement.py",
            "ui/window_placement.py",
            "ui/title_controls.py",
        ),
    ),
    ("Title effect, Bind lines and scrolling text", ("ui/title_effect.py", "ui/profile_marquee.py")),
)

CSS = r"""
@page {
  size: letter;
  margin: 0.85in 0.9in 0.8in 0.9in;
  @top-left { content: "SPACENAVIGATOR MAPPER / FULL EDITOR README"; font: 6.5pt "DejaVu Sans", "Segoe UI", sans-serif; letter-spacing: 0.08em; color: #64748b; }
  @top-right { content: "REFERENCE MANUAL"; font: 6.5pt "DejaVu Sans", "Segoe UI", sans-serif; letter-spacing: 0.06em; color: #64748b; }
  @bottom-left { content: "SpaceNavigator Mapper"; font: 6.5pt "DejaVu Sans", "Segoe UI", sans-serif; color: #64748b; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 6.5pt "DejaVu Sans", "Segoe UI", sans-serif; color: #64748b; }
}
html { font-size: 10.5pt; }
body { font-family: "DejaVu Sans", "Segoe UI", Verdana, sans-serif; color: #1f2937; line-height: 1.5; margin: 0; }
h1, h2, h3, h4 { color: #1e3a5f; font-weight: bold; break-after: avoid; page-break-after: avoid; }
h1.title { font-size: 22pt; line-height: 1.2; margin: 0.5in 0 0.25in; padding-bottom: 6pt; border-bottom: 2.5pt solid #2c5f8f; }
h2 { font-size: 14.5pt; margin: 20pt 0 10pt; padding-bottom: 4pt; border-bottom: 0.75pt solid #e2e8f0; }
h3 { font-size: 11.5pt; color: #24507a; margin: 14pt 0 6pt; }
h4 { font-size: 9.5pt; color: #24507a; margin: 12pt 0 4pt; }
p { margin: 0 0 8pt; }
strong { color: #1e3a5f; }
a { color: #24507a; text-decoration: none; }
code { font-family: "DejaVu Sans Mono", Consolas, monospace; font-size: 0.86em; color: #334155; }
ul, ol { margin: 0 0 8pt; padding-left: 20pt; }
li { margin: 1pt 0; }
ul.task-list { list-style: none; padding-left: 4pt; }
ul.task-list input { margin: 0 6pt 0 0; vertical-align: -1pt; }
blockquote { margin: 8pt 0 12pt; padding: 8pt 14pt; background: #f4f7fa; border-left: 3.5pt solid #cbd5e1; color: #4a5568; }
blockquote strong { color: #1e3a5f; }
blockquote p:last-child { margin-bottom: 0; }
hr { border: 0; border-top: 0.75pt solid #e2e8f0; margin: 16pt 0; }
nav#TOC { margin: 6pt 0 16pt; padding: 10pt 16pt 8pt; background: #f4f7fa; border-left: 3.5pt solid #3b6ea5; font-size: 7.5pt; }
nav#TOC p.toc-title { margin: 0 0 4pt; color: #1f2937; }
nav#TOC ul { list-style: none; margin: 0; padding-left: 14pt; }
nav#TOC li { margin: 3pt 0; }
nav#TOC a { color: #1f2937; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 12pt; font-size: 7.6pt; line-height: 1.4; border-top: 1pt solid #1e3a5f; border-bottom: 1pt solid #1e3a5f; }
thead { display: table-header-group; }
tr { break-inside: avoid; page-break-inside: avoid; }
th { background: #e8eef6; color: #1e3a5f; text-align: left; font-weight: bold; padding: 4pt 5pt; border-bottom: 1pt solid #1e3a5f; vertical-align: top; }
td { padding: 3pt 5pt; border: 0.5pt solid #dde3ea; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f5f8fb; }
td:first-child strong { color: #1e3a5f; }
td code { font-size: 0.95em; }
table.functions td:first-child code { word-break: break-all; color: #1f2937; }
table.functions td:nth-child(2), table.functions th:nth-child(2) { text-align: right; white-space: nowrap; }
.inventory-note { font-size: 9pt; color: #4a5568; }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>$pagetitle$</title>
<style>/*CSS*/</style>
</head>
<body>
<h1 class="title">$title$</h1>
<nav id="TOC" role="doc-toc"><p class="toc-title">$title$</p>
$table-of-contents$
</nav>
$body$
</body>
</html>
"""


def read_version():
    """VERSION and REVISION_DATE from spnav_mapper/version.py."""
    tree = ast.parse((PACKAGE / "version.py").read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value.value
    return values["VERSION"], values["REVISION_DATE"]


def purpose(doc):
    """The first paragraph of a docstring on one line (its first sentence when long)."""
    first = " ".join((doc or "").strip().split("\n\n")[0].split())
    if len(first) > 190:
        match = re.match(r"(.+?[.!?])(\s|$)", first)
        if match:
            first = match.group(1)
    return first


def function_inventory(package=PACKAGE):
    """(module, qualified name, line, purpose) for every top-level function and method."""
    rows = []
    for path in sorted(package.rglob("*.py")):
        module = path.relative_to(package).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                rows.append((module, node.name, node.lineno, purpose(ast.get_docstring(node))))
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        rows.append(
                            (module, f"{node.name}.{sub.name}", sub.lineno, purpose(ast.get_docstring(sub)))
                        )
    return rows


def _cell(text):
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("*", "\\*")


def reference_markdown(rows, version):
    """Section 8's body: an introduction, then one table per module, grouped."""
    by_module = {}
    for module, name, line, text in rows:
        by_module.setdefault(module, []).append((name, line, text))
    grouped = {m for _, modules in GROUPS for m in modules}
    groups = [(title, [m for m in modules if m in by_module]) for title, modules in GROUPS]
    others = sorted(m for m in by_module if m not in grouped)
    if others:
        groups.append(("Other modules", others))
    out = [
        "The inventory lists every **top-level function and class method** of the `spnav_mapper` "
        f"package of {version}, with its source line and purpose (the first line of its docstring). "
        "It is written by `tools/build_readme_pdf.py` from the source, so it stays complete when the "
        "code changes. An underscore prefix means an internal helper or event handler; it does not "
        "imply a user-visible control. Nested callbacks are not listed. Line numbers refer to "
        f"{version} and change in later releases.",
        "",
        f"**{len(rows)} functions and methods in {len(by_module)} modules.**",
        "",
    ]
    number = 0
    for title, modules in groups:
        if not modules:
            continue
        number += 1
        out += [f"### 8.{number}. {title}", ""]
        for module in modules:
            entries = by_module[module]
            out += [
                f"#### `{module}` — {len(entries)} function{'s' if len(entries) != 1 else ''}",
                "",
                '<div class="functions">',
                "",
                "| Function / method                 | Line | Purpose                                                    |",
                "|-----------------------------------|-----:|------------------------------------------------------------|",
            ]
            for name, line, text in entries:
                out.append(f"| `{name}()` | {line} | {_cell(text) or '—'} |")
            out += ["", "</div>", ""]
    return "\n".join(out).rstrip() + "\n"


def update_markdown(text, version, date, reference):
    """The README Markdown with its version line and section 8 brought up to date."""
    text, count = re.subn(
        r"^\*\*Version:\*\* .*?(  )?$", f"**Version:** {version} ({date})  ", text, count=1, flags=re.M
    )
    if not count:
        raise SystemExit("The README has no **Version:** line.")
    start, end = text.find(BEGIN), text.find(END)
    if start < 0 or end < start:
        raise SystemExit("The README has no function-reference markers.")
    return text[: start + len(BEGIN)] + "\n\n" + reference + "\n" + text[end:]


def find_pandoc():
    found = shutil.which("pandoc")
    if not found:
        raise SystemExit("pandoc was not found. Install it from https://pandoc.org/installing.html")
    return found


def find_browser():
    """Chrome, Chromium or Edge: the first one installed."""
    names = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for base in (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ):
        if not base:
            continue
        for rel in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
            candidate = Path(base) / rel
            if candidate.is_file():
                return str(candidate)
    raise SystemExit("Chrome or Edge was not found; it prints the HTML to PDF.")


def markdown_to_html(markdown, version):
    """The README as a standalone HTML page in the reference-manual style."""
    lines = markdown.split("\n")
    title = lines[0].lstrip("#").strip()
    body = "\n".join(lines[1:])
    with tempfile.TemporaryDirectory() as tmp:
        template = Path(tmp) / "readme.html5"
        template.write_text(TEMPLATE, encoding="utf-8")
        result = subprocess.run(
            [
                find_pandoc(),
                "--from=markdown-implicit_figures",
                "--to=html5",
                "--standalone",
                f"--template={template}",
                "--toc",
                "--toc-depth=2",
                "--metadata",
                f"title={title}",
                "--metadata",
                f"pagetitle=SpaceNavigator Mapper — Full Editor README {version}",
            ],
            input=body,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    html = result.stdout.replace("/*CSS*/", CSS)
    # The function tables are wrapped in <div class="functions">: give the tables the class.
    html = re.sub(r'(<div class="functions">\s*<table)', r'\1 class="functions"', html)
    return html


def html_to_pdf(html, pdf):
    """Print the HTML to `pdf` with headless Chrome or Edge."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "SpaceNavigator_Mapper_README.html"
        page.write_text(html, encoding="utf-8")
        out = Path(tmp) / "out.pdf"
        command = [
            find_browser(),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out}",
            page.as_uri(),
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            command.insert(1, "--no-sandbox")  # Chrome refuses to run as root otherwise
        subprocess.run(command, check=True, capture_output=True, timeout=180)
        if not out.is_file() or out.read_bytes()[:5] != b"%PDF-":
            raise SystemExit("The browser did not write a PDF.")
        qpdf = shutil.which("qpdf")
        if qpdf:  # optional: object streams make the file about a third of the size
            small = Path(tmp) / "small.pdf"
            done = subprocess.run(
                [
                    qpdf,
                    "--object-streams=generate",
                    "--compress-streams=y",
                    "--recompress-flate",
                    "--compression-level=9",
                    str(out),
                    str(small),
                ],
                capture_output=True,
            )
            if done.returncode in (0, 3) and small.is_file():  # 3: warnings only
                out = small
        shutil.copyfile(out, pdf)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--md-only", action="store_true", help="update the Markdown, do not print the PDF")
    args = parser.parse_args(argv)
    version, date = read_version()
    rows = function_inventory()
    text = update_markdown(
        MARKDOWN.read_text(encoding="utf-8"), version, date, reference_markdown(rows, version)
    )
    MARKDOWN.write_text(text, encoding="utf-8", newline="\n")
    missing = [f"{m}::{n}" for m, n, _, t in rows if not t]
    print(f"{MARKDOWN.relative_to(ROOT)}: {version}, {len(rows)} functions")
    if missing:
        print(f"  {len(missing)} without a docstring: " + ", ".join(missing[:10]))
    if args.md_only:
        return 0
    html_to_pdf(markdown_to_html(text, version), PDF)
    print(f"{PDF.relative_to(ROOT)}: {PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
