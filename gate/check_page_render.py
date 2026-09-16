#!/usr/bin/env python3
"""check_page_render.py — render-quality gate for a Xactly Extend page definition.

The structural gate (validate_page) proves a page is well-formed and wired. It cannot see the defects
that make a shipped dashboard look broken. Those are here — each check cites its rule
in knowledge/dashboard_render_defects.md:

  P1 (R9)   a label/Custom section header immediately above a data control that renders the SAME title
            -> the page shows the heading, then "Table - <same heading>" right under it       ERROR
  P2 (R10)  a table with no maxHeight and a large itemsPerPage, followed by another control
            -> the unbounded table renders over whatever comes next                           ERROR
  P3 (R15)  placeholder copy shipped in controlData/html ("TODO", "Coming soon",
            "Verification in progress", "undefined", "lorem")                                 ERROR
  P4 (R13)  a variable owned by a selector that no shipped query takes as a :param and no other
            control binds  (needs --queries; skipped otherwise)                               ERROR
  P5 (R11)  a control whose copy claims role gating ("visible for managers", "role:") while no
            control in the page is hidden by default                                          WARN
  P6 (R15)  meter/progress/gauge markup with no bound field in the same control               WARN
  P7 (R16)  a visual row whose layoutSize values do not sum to ~100 (ragged / half-empty row) ERROR

Usage:  python check_page_render.py <page.json> [<page2.json> ...] [--queries <dir>]
Exit 0 iff no ERRORs.
"""
import sys, os, re, json, glob

MAX_UNBOUNDED_ROWS = 25          # rows a table may render before it needs a maxHeight
ROW_SUM_TOLERANCE = 1.0          # 33.33*3 and 16.66*6 land just under 100
ALLOWED_LAYOUT = {100, 66.66, 50, 33.33, 25, 16.66}

PLACEHOLDER_RE = re.compile(r"\b(TODO|FIXME|coming soon|verification in progress|undefined|lorem ipsum|"
                            r"placeholder|tbd|xxx+)\b", re.I)
METER_RE = re.compile(r"(progress|meter|gauge|bar-fill|width\s*:\s*\d+%)", re.I)
ROLE_COPY_RE = re.compile(r"(visible (for|to) (managers|leaders)|role\s*[:=]\s*(ic|manager|leader)|"
                          r"managers? (&|and) leaders?)", re.I)
DATA_KINDS = ("table", "chart", "composedChart", "grid")
SELECTOR_KINDS = ("dropdown", "input", "variableConfigurator")
# Invisible / overlay controls — they don't occupy the visual grid (R16).
LAYOUT_SKIP_TYPES = {"PageLoader", "variableConfigurator", "Timer"}
# When layoutSize is omitted, Extend / the assembler treat these as full-width.
LAYOUT_DEFAULT_100 = {"table", "grid", "composedChart", "chart", "label", "input", "exportPagePDF"}
# Assembler defaults for other visible kinds (same as gate/extend_build.py).
LAYOUT_DEFAULT_OTHER = {
    "dropdown": 25.0,
    "tile": 25.0,
    "Custom": 33.33,
    "button": 16.66,
}


def props_of(doc):
    return (((doc.get("pageSchema") or {}).get("controlSchema") or {}).get("schema") or {}).get("properties") or {}


def ordered_controls(props):
    """Controls in render order (by the numeric suffix of control_N, else insertion order)."""
    def key(item):
        m = re.search(r"(\d+)$", item[0])
        return (0, int(m.group(1))) if m else (1, 0)
    return [(k, v) for k, v in sorted(props.items(), key=key) if isinstance(v, dict)]


def title_of(ctrl):
    for k in ("title", "label", "headerName", "displayName"):
        v = ctrl.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return heading_of(ctrl)


def heading_of(ctrl):
    """The heading a label/Custom control renders: the first h1-h4 (else the first text line) of its markup."""
    html = html_of(ctrl)
    if not html:
        return ""
    m = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", html, re.I | re.S)
    text = m.group(1) if m else html
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\{\{[^}]*\}\}", " ", text)
    for line in (l.strip() for l in text.splitlines()):
        if line:
            return re.sub(r"\s+", " ", line)
    return ""


def html_of(ctrl):
    parts = []
    for k in ("controlData", "html", "template", "content"):
        v = ctrl.get(k)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            parts.append(json.dumps(v))
    return "\n".join(parts)


def text_of(ctrl):
    return title_of(ctrl) + "\n" + html_of(ctrl)


def norm(s):
    """Normalize a title for comparison: drop a 'Table - '/'Chart - ' prefix, punctuation, case."""
    s = re.sub(r"^\s*(table|chart|grid)\s*[-–:]\s*", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def bound_fields(ctrl):
    """Field names this control binds (boundToField / column / columns / chart keys)."""
    out = set()
    blob = json.dumps(ctrl)
    out |= set(re.findall(r'"(?:boundToField|field|column|dataKey|valueField|displayField)"\s*:\s*"([^"]+)"', blob))
    out |= set(re.findall(r"\{\{\s*([a-z0-9_.]+)\s*\}\}", blob, re.I))
    return {f for f in out if f}


def owned_vars(ctrl):
    return {v.get("name") for v in (ctrl.get("variables") or []) if isinstance(v, dict) and v.get("name")}


def layout_width(ctrl):
    """Effective grid width for a visible control. None => skip (invisible driver)."""
    ctype = ctrl.get("type", "")
    if ctype in LAYOUT_SKIP_TYPES:
        return None
    ls = ctrl.get("layoutSize")
    if ls in (None, ""):
        if ctype in LAYOUT_DEFAULT_100:
            return 100.0
        return LAYOUT_DEFAULT_OTHER.get(ctype)  # None => unknown type, skip
    try:
        return float(ls)
    except (TypeError, ValueError):
        return None


def pack_visual_rows(controls):
    """Greedy left-to-right row packing of visible controls (same model Extend uses)."""
    rows, row, acc = [], [], 0.0
    for cid, c in controls:
        w = layout_width(c)
        if w is None:
            continue
        if row and acc + w > 100.0 + ROW_SUM_TOLERANCE:
            rows.append((row, acc))
            row, acc = [], 0.0
        row.append((cid, c.get("type", ""), w))
        acc += w
        if abs(acc - 100.0) <= ROW_SUM_TOLERANCE:
            rows.append((row, acc))
            row, acc = [], 0.0
    if row:
        rows.append((row, acc))
    return rows


def query_params(qdir):
    """Every :v_param referenced by the shipped queries in <dir> (.sql or query-object .json)."""
    params = set()
    for p in glob.glob(os.path.join(qdir, "**", "*.sql"), recursive=True) + \
             glob.glob(os.path.join(qdir, "**", "*.json"), recursive=True):
        with open(p, encoding="utf-8", errors="ignore") as f:
            params |= set(re.findall(r":(v_[a-z0-9_]+)", f.read(), re.I))
    return params


def check_page(path, errors, warns, qparams=None):
    doc = json.load(open(path, encoding="utf-8"))
    tag = os.path.basename(path)
    controls = ordered_controls(props_of(doc))
    if not controls:
        warns.append(f"{tag}: no controls found — is this a page definition?")
        return

    blob = json.dumps(doc)
    any_hidden = bool(re.search(r'"(shouldRenderHidden|hidden)"\s*:\s*true', blob, re.I))

    for i, (cid, c) in enumerate(controls):
        ctype = c.get("type", "")
        title = title_of(c)

        # P1 — the same heading rendered twice: a section header above its own table/chart
        # (an input/search box may sit between the header and the table, so look ahead a couple of controls)
        if title and norm(title):
            for nxt_id, nxt in controls[i + 1:i + 3]:
                if nxt.get("type") in DATA_KINDS and norm(title) == norm(title_of(nxt)):
                    errors.append(f"{tag}:{cid}/{nxt_id} both render the heading '{title}' — title the section OR "
                                  f"the data control, not both (the page shows 'X' then 'Table - X')")
                    break

        # P2 — an unbounded table renders over whatever follows it
        if ctype in ("table", "grid") and i + 1 < len(controls):
            per_page = ((c.get("pagination") or {}).get("itemsPerPage"))
            if c.get("maxHeight") in (None, "", 0) and isinstance(per_page, int) and per_page > MAX_UNBOUNDED_ROWS:
                errors.append(f"{tag}:{cid} renders up to {per_page} rows with no maxHeight — an unbounded, "
                              f"data-driven height overlaps the controls placed after it; set maxHeight or cap "
                              f"itemsPerPage at {MAX_UNBOUNDED_ROWS}")

        # P3 — placeholder copy
        m = PLACEHOLDER_RE.search(html_of(c))
        if m:
            errors.append(f"{tag}:{cid} ships placeholder copy '{m.group(0)}' in its markup — bind a real value "
                          f"or remove the element")

        # P5 — role gating written, not wired
        if ROLE_COPY_RE.search(text_of(c)) and not any_hidden:
            warns.append(f"{tag}:{cid} claims role gating in its copy but no control on the page is hidden by "
                         f"default — role gating is wiring (hidden:true + a role channel), not text")

        # P6 — unbound meter
        if METER_RE.search(html_of(c)) and not bound_fields(c):
            warns.append(f"{tag}:{cid} draws a progress/meter element with no bound field — bind its fill or "
                         f"drop the visual (a static bar reads as 0%)")

        # P7a — layoutSize must be an allowed grid width when set on a visible control
        w = layout_width(c)
        if w is not None and c.get("layoutSize") not in (None, ""):
            if not any(abs(w - a) < 0.01 for a in ALLOWED_LAYOUT):
                errors.append(f"{tag}:{cid} layoutSize={c.get('layoutSize')!r} is not an allowed grid width "
                              f"({sorted(ALLOWED_LAYOUT)}); use a size that tiles a row to 100")

    # P7 — every visual row's layoutSizes must sum to ~100 (R16)
    for row, total in pack_visual_rows(controls):
        if abs(total - 100.0) <= ROW_SUM_TOLERANCE:
            continue
        desc = " + ".join(f"{cid}:{t}@{w:g}" for cid, t, w in row)
        errors.append(f"{tag}: visual row sums to {total:g}% (need ~100) — {desc}. "
                      f"Size siblings so N×width=100 (2→50, 3→33.33, 4→25, 6→16.66); "
                      f"split 5 filters into two rows; tables/charts/labels stay at 100 alone")

    # P4 — a selector variable nobody consumes (needs the shipped queries: page-embedded xSQL alone
    # can't show that a tenant view reads the param)
    if qparams is None:
        return
    consumers = {}
    for cid, c in controls:
        for f in bound_fields(c):
            consumers.setdefault(f, set()).add(cid)
    params_used = set(re.findall(r":(v_[a-z0-9_]+)", blob, re.I)) | set(qparams)
    for cid, c in controls:
        if c.get("type") not in SELECTOR_KINDS:
            continue
        for var in owned_vars(c):
            if not var:
                continue
            others = consumers.get(var, set()) - {cid}
            if var not in params_used and not others:
                errors.append(f"{tag}:{cid} owns variable '{var}' that nothing consumes — no view takes it as a "
                              f":param and no other control binds it (a selector that changes nothing)")


def main():
    args = sys.argv[1:]
    qdir = None
    if "--queries" in args:
        i = args.index("--queries")
        qdir = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(2)
    qparams = query_params(qdir) if qdir else None

    errors, warns = [], []
    for p in args:
        if not os.path.exists(p):
            print(f"ERROR: {p} not found")
            sys.exit(1)
        check_page(p, errors, warns, qparams)

    print(f"pages checked: {len(args)}" + (f" | query params seen: {len(qparams)}" if qparams is not None
                                           else " | P4 skipped (no --queries)"))
    if errors:
        print(f"\n✗ {len(errors)} ERROR(S):")
        for e in errors:
            print("  ERROR:", e)
    if warns:
        print(f"\n⚠ {len(warns)} WARNING(S):")
        for w in warns:
            print("  WARN: ", w)
    if not errors and not warns:
        print("\n✓ PASS — no render-quality issues.")
    elif not errors:
        print(f"\n✓ PASS (with {len(warns)} warning(s) to review).")
    else:
        print(f"\n✗ FAIL — {len(errors)} error(s).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
