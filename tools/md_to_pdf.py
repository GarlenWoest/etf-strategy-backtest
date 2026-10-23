"""Convert a project Markdown file to a clean PDF with headless Google Chrome (already installed; nothing new needed).

Handles the Markdown this project uses: headings, paragraphs, bullet lists (nested by indentation), tables, images on
their own line (embedded as figures), **bold**, _italic_, `code` and [links](url). The first H1 and the italic line under
it go on a title page; later pages are numbered "Page n of N" in the footer (CSS page-margin boxes).
Intermediate files (HTML, Chrome profile) go to tmp/ inside the project.

Usage: .venv/bin/python -I tools/md_to_pdf.py SUMMARY.md SUMMARY.pdf
"""
import html
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: Letter; margin: 0.6in 0.65in 0.7in 0.65in;
        @bottom-center { content: "Page " counter(page) " of " counter(pages); font: 9pt -apple-system, Helvetica, Arial, sans-serif; color: #666; } }
@page :first { @bottom-center { content: none; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font: 9.4pt/1.34 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: #1a1a1a; }
.title-page { height: 9.5in; display: flex; flex-direction: column; justify-content: center; break-after: page; }
.title-page .kicker { font-size: 11pt; letter-spacing: .12em; text-transform: uppercase; color: #8a6d1f; margin-bottom: 14pt; }
.title-page h1 { font-size: 26pt; line-height: 1.2; margin: 0 0 18pt; border: 0; }
.title-page .sub { font-size: 11.5pt; color: #444; max-width: 5.6in; }
.title-page .meta { margin-top: 36pt; font-size: 10.5pt; color: #555; border-top: 2px solid #8a6d1f; padding-top: 10pt; width: 4in; }
h2 { font-size: 13pt; margin: 13pt 0 4pt; padding-bottom: 3pt; border-bottom: 1.5px solid #d9cfb4; break-after: avoid; }
h3 { font-size: 11pt; margin: 9pt 0 3pt; break-after: avoid; }
p { margin: 3pt 0 5pt; }
ul { margin: 2pt 0 5pt; padding-left: 16pt; } li { margin: 1pt 0; } li ul { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 7pt; font-size: 8.2pt; break-inside: avoid; }
th, td { border: 1px solid #cfcfcf; padding: 2.2pt 4pt; text-align: left; vertical-align: top; }
th { background: #f3efe4; font-weight: 600; } tr:nth-child(even) td { background: #fafafa; }
figure { margin: 6pt 0 8pt; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 3.5in; } figcaption { font-size: 8.5pt; color: #555; margin-top: 3pt; }
code { font: 8.8pt Menlo, monospace; background: #f2f2f2; padding: 0 2pt; border-radius: 2pt; }
a { color: #1f4e8a; text-decoration: none; }
td.nowrap { white-space: nowrap; }
"""


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], cells[2:]
    out = ["<table><thead><tr>" + "".join("<th>%s</th>" % inline(c) for c in head) + "</tr></thead><tbody>"]
    cell = lambda c: '<td class="nowrap">%s</td>' % inline(c) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c) else "<td>%s</td>" % inline(c)
    out += ["<tr>" + "".join(cell(c) for c in r) + "</tr>" for r in body]
    return "\n".join(out) + "</tbody></table>"


def bullets(lines):
    """Nested <ul> from '- ' items; indented non-bullet lines continue the previous item."""
    out, stack = [], []
    for ln in lines:
        ind = len(ln) - len(ln.lstrip())
        txt = ln.strip()
        if txt.startswith("- "):
            while stack and ind < stack[-1]:
                out.append("</li></ul>")
                stack.pop()
            if not stack or ind > stack[-1]:
                out.append("<ul>")
                stack.append(ind)
            else:
                out.append("</li>")
            item = txt[2:]
            out.append("<li>" + ("&#9744;&nbsp;" + inline(item[4:]) if item.startswith("[ ] ") else inline(item)))
        elif txt:
            out.append("<p>%s</p>" % inline(txt))
    while stack:
        out.append("</li></ul>")
        stack.pop()
    return "\n".join(out)


def convert(md, base):
    lines = md.splitlines()
    body, i = [], 0
    title = sub = None
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("# ") and title is None:
            title = ln[2:].strip()
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].startswith("_") and lines[j].rstrip().endswith("_"):
                sub, i = lines[j].strip()[1:-1], j + 1
            else:
                i += 1
            continue
        m = re.match(r"^(#{2,4}) (.*)", ln)
        if m:
            body.append("<h%d>%s</h%d>" % (len(m.group(1)), inline(m.group(2)), len(m.group(1))))
            i += 1
            continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", ln)
        if m:
            src = (base / m.group(2)).resolve()
            if not src.exists():
                raise FileNotFoundError(src)
            body.append('<figure><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>' % (
                src.as_uri(), html.escape(m.group(1)), inline(m.group(1))))
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            body.append(table(lines[i:j]))
            i = j
            continue
        if ln.lstrip().startswith("- "):
            j = i
            while j < len(lines) and (lines[j].lstrip().startswith("- ") or (lines[j].startswith("  ") and lines[j].strip())
                                      or (not lines[j].strip() and j + 1 < len(lines) and lines[j + 1].startswith("  "))):
                j += 1
            body.append(bullets(lines[i:j]))
            i = j
            continue
        j = i
        while j < len(lines) and lines[j].strip() and not re.match(r"^(#|\||- |!\[)", lines[j].lstrip()):
            j += 1
        body.append("<p>%s</p>" % inline(" ".join(x.strip() for x in lines[i:j])))
        i = j
    tp = ('<section class="title-page"><div class="kicker">trading-research</div><h1>%s</h1>%s'
          '<div class="meta">Project summary &middot; %s<br>Garlen Woest</div></section>' % (
              inline(title or "Summary"), '<div class="sub">%s</div>' % inline(sub) if sub else "",
              date.today().strftime("%B %-d, %Y")))
    return "<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body>%s\n%s</body></html>" % (
        html.escape(title or "Summary"), CSS, tp, "\n".join(body))


def main(src, dst):
    src, dst = (ROOT / src).resolve(), (ROOT / dst).resolve()
    for p in (src, dst):
        if not str(p).startswith(str(ROOT)):
            sys.exit("files must be inside the project")
    tmp = ROOT / "tmp" / "pdf_build"
    tmp.mkdir(parents=True, exist_ok=True)
    page = tmp / (src.stem + ".html")
    page.write_text(convert(src.read_text(), src.parent))
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                        "--user-data-dir=%s" % (tmp / "chrome-profile"), "--no-pdf-header-footer",
                        "--print-to-pdf=%s" % dst, page.as_uri()], capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not dst.exists():
        sys.exit("Chrome failed: %s" % (r.stderr or r.stdout)[-500:])
    print("wrote %s (%d bytes)" % (dst, dst.stat().st_size))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
