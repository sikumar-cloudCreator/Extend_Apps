#!/usr/bin/env python3
"""
frd_flows.py — Stage before any code generation (user points 1 & 2).

Entry: every session offers two paths —
  UPLOAD_FRD   : user provides an FRD file -> read to text -> ready for finalize.
  GENERATE_FRD : user provides plain-English requirements -> Opus writes an FRD (EFM template)
                 -> exported as a downloadable Word .docx -> user reviews -> finalize.

Hard gate (point 2): NO build/code/JSON generation until the FRD is FINALIZED. `FRDSession.guard_build()`
raises until then; the orchestrator must call it before any architect/xSQL/page step.

Deterministic parts (read FRD, markdown->docx export, the session gate) need NO API key and are testable.
Only `generate_frd()` calls Opus (needs ANTHROPIC_API_KEY).

CLI:
    python frd_flows.py --to-docx sample_frd.md out.docx     # markdown FRD -> Word doc
    python frd_flows.py --read some_frd.docx                  # extract FRD text
"""
import os, re, sys, html, zipfile, subprocess, tempfile
from dataclasses import dataclass, field
from enum import Enum

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(os.path.dirname(HERE), "prompts", "20_frd_author.md")
TEMPLATE_PATH = os.path.join(os.path.dirname(HERE), "knowledge", "frd_template.md")
MODEL = "claude-opus-4-8"


class Mode(str, Enum):
    UPLOAD = "upload_frd"
    GENERATE = "generate_frd"


ENTRY_CHOICES = [
    {"id": Mode.UPLOAD.value, "label": "Upload FRD", "hint": "You already have an FRD file to build from."},
    {"id": Mode.GENERATE.value, "label": "Generate FRD", "hint": "Describe requirements in plain English; I'll write the FRD and give you a Word doc."},
]


# ---- read an uploaded FRD (.docx / .md / .txt) -> text ---------------------------------------
def read_frd(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
        paras = re.split(r"</w:p>", xml)
        out = []
        for p in paras:
            txt = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
            txt = re.sub(r"<[^>]+>", "", txt)   # drop any stray runs textutil leaves in list items
            txt = html.unescape(txt).strip()
            if txt:
                out.append(txt)
        return "\n".join(out)
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


# ---- markdown FRD -> Word .docx (dependency-free via macOS textutil) --------------------------
_INLINE = [(re.compile(r"\*\*(.+?)\*\*"), r"<b>\1</b>"),
           (re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)"), r"<i>\1</i>"),
           (re.compile(r"`(.+?)`"), r"<code>\1</code>")]


def _inline(s: str) -> str:
    s = html.escape(s)
    for pat, rep in _INLINE:
        s = pat.sub(rep, s)
    return s


def markdown_to_html(md: str) -> str:
    """Minimal markdown -> HTML for the FRD subset: h1-h4, ul/ol, pipe tables, paragraphs, inline."""
    lines = md.splitlines()
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        # heading
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>"); i += 1; continue
        # table block (pipe rows with a separator line)
        if "|" in ln and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            header = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i]:
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            t = ["<table border='1' cellspacing='0' cellpadding='4'><tr>" +
                 "".join(f"<th>{_inline(h)}</th>" for h in header) + "</tr>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
            t.append("</table>")
            out.append("".join(t)); continue
        # unordered list
        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>"); i += 1
            out.append("<ul>" + "".join(items) + "</ul>"); continue
        # ordered list
        if re.match(r"^\s*\d+\.\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(f"<li>{_inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))}</li>"); i += 1
            out.append("<ol>" + "".join(items) + "</ol>"); continue
        # blank / paragraph
        if not ln.strip():
            i += 1; continue
        out.append(f"<p>{_inline(ln)}</p>"); i += 1
    style = ("<style>body{font-family:'Century Gothic',Calibri,Arial,sans-serif;font-size:11pt;}"
             "h1{font-size:16pt}h2{font-size:13pt}h3{font-size:11.5pt}"
             "table{border-collapse:collapse;font-size:10pt}th{background:#eee;text-align:left}</style>")
    return f"<html><head><meta charset='utf-8'>{style}</head><body>{''.join(out)}</body></html>"


def markdown_to_docx(md: str, out_path: str) -> str:
    """Render an FRD (markdown) to a Word .docx. Uses macOS `textutil` (no pip deps)."""
    htmltext = markdown_to_html(md)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(htmltext); tmp = tf.name
    try:
        subprocess.run(["textutil", "-convert", "docx", "-output", out_path, tmp], check=True)
    finally:
        os.unlink(tmp)
    return out_path


# ---- generate an FRD from plain English (Opus) -----------------------------------------------
def generate_frd(requirements: str, extra_context: str = "") -> str:
    """plain-English requirements -> FRD markdown (EFM template). Needs ANTHROPIC_API_KEY."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("pip install anthropic to generate an FRD")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("set ANTHROPIC_API_KEY to generate an FRD (read/export work without it)")
    system = open(PROMPT_PATH).read()
    template = open(TEMPLATE_PATH).read() if os.path.exists(TEMPLATE_PATH) else ""
    user = (f"REQUIREMENTS (plain English):\n{requirements}\n\n"
            + (f"ADDITIONAL CONTEXT:\n{extra_context}\n\n" if extra_context else "")
            + f"FRD TEMPLATE TO FOLLOW:\n{template}")
    client = anthropic.Anthropic()
    resp = client.messages.create(model=MODEL, max_tokens=8000, system=system,
                                  messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


# ---- session state + the finalize-before-build gate (point 2) --------------------------------
class BuildBlocked(RuntimeError):
    pass


@dataclass
class FRDSession:
    mode: Mode | None = None
    requirements: str = ""          # plain English (generate path)
    frd_markdown: str = ""          # the working FRD (generated or read from upload)
    docx_path: str | None = None    # downloadable doc (generate path)
    source_path: str | None = None  # uploaded file (upload path)
    finalized: bool = False
    history: list = field(default_factory=list)  # user comments/iterations (feeds learning later)

    # entry
    def choose(self, mode: Mode) -> dict:
        self.mode = Mode(mode)
        return {"mode": self.mode.value,
                "next": "upload a file" if self.mode == Mode.UPLOAD else "send plain-English requirements"}

    # upload path
    def load_upload(self, path: str) -> str:
        self.source_path = path
        self.frd_markdown = read_frd(path)
        self.finalized = False
        return self.frd_markdown

    # generate path
    def draft_from_requirements(self, requirements: str, out_docx: str, extra_context: str = "") -> dict:
        self.requirements = requirements
        self.frd_markdown = generate_frd(requirements, extra_context)
        self.docx_path = markdown_to_docx(self.frd_markdown, out_docx)
        self.finalized = False
        return {"frd_markdown": self.frd_markdown, "docx_path": self.docx_path}

    def revise(self, comment: str, out_docx: str | None = None) -> dict:
        """User comment -> regenerate FRD. Also logs the comment for the learning loop (point 5)."""
        self.history.append(comment)
        self.frd_markdown = generate_frd(self.requirements,
                                         extra_context=f"Prior FRD:\n{self.frd_markdown}\n\nRevise per: {comment}")
        if out_docx or self.docx_path:
            self.docx_path = markdown_to_docx(self.frd_markdown, out_docx or self.docx_path)
        self.finalized = False
        return {"frd_markdown": self.frd_markdown, "docx_path": self.docx_path}

    # the gate
    def finalize(self) -> dict:
        if not self.frd_markdown.strip():
            raise BuildBlocked("no FRD to finalize yet")
        self.finalized = True
        return {"finalized": True, "next": "build may start"}

    def guard_build(self):
        """Call before ANY code/JSON generation. Raises until the user finalizes the FRD (point 2)."""
        if not self.finalized:
            raise BuildBlocked("FRD is not finalized — no code/JSON generation until the user finalizes it.")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--to-docx":
        md = open(sys.argv[2], encoding="utf-8").read()
        print("wrote:", markdown_to_docx(md, sys.argv[3]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "--read":
        print(read_frd(sys.argv[2])[:3000])
    else:
        print(__doc__)
